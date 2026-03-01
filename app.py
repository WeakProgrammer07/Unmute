import os
import json
import base64
import asyncio
import threading
import uuid
import numpy as np
import sounddevice as sd
import websockets
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from flask import Flask, render_template
from flask_socketio import SocketIO

load_dotenv()

eleven_client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))

VOICE_ID = "RyYIThp5u2AKF8D8kN6R"
SAMPLE_RATE = 16000
TRIGGER_DELAY = 1.0  # seconds before auto-firing

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

trigger_words = ["questions", "thoughts", "liam", "add anything", "feedback"]
triggers_enabled = True

# Queue: list of dicts {id, text, path}
response_queue = []
queue_lock = threading.Lock()

afplay_proc = None
pending_fire_timer = None


def get_blackhole_index():
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if "blackhole" in dev["name"].lower():
            return i
    return None


async def _listen_loop():
    device_index = get_blackhole_index()
    label = "BlackHole" if device_index is not None else "default mic"
    socketio.emit("status", {"msg": f"Listening via {label}", "state": "listening"})

    uri = "wss://api.elevenlabs.io/v1/speech-to-text/realtime?model_id=scribe_v2_realtime&inactivity_timeout=300&endpointing=200"
    headers = {"xi-api-key": os.getenv("ELEVEN_API_KEY")}

    async with websockets.connect(uri, additional_headers=headers) as ws:
        async def send_audio():
            loop = asyncio.get_event_loop()
            queue = asyncio.Queue()

            def audio_callback(indata, frames, time, status):
                loop.call_soon_threadsafe(queue.put_nowait, indata.copy())

            with sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                device=device_index, blocksize=4096, callback=audio_callback
            ):
                while True:
                    chunk = await queue.get()
                    audio_b64 = base64.b64encode(chunk.tobytes()).decode()
                    await ws.send(json.dumps({
                        "message_type": "input_audio_chunk",
                        "audio_base_64": audio_b64,
                        "sample_rate": SAMPLE_RATE
                    }))

        async def receive_transcripts():
            async for message in ws:
                data = json.loads(message)
                msg_type = data.get("message_type", "")
                if msg_type == "committed_transcript":
                    text = data.get("text", "").strip()
                    if text:
                        socketio.emit("transcript", {"text": text, "final": True})
                        check_trigger(text)
                elif msg_type == "partial_transcript":
                    text = data.get("text", "").strip()
                    if text:
                        socketio.emit("transcript", {"text": text, "final": False})
                        check_trigger(text)

        await asyncio.gather(send_audio(), receive_transcripts())


def check_trigger(text):
    global pending_fire_timer
    with queue_lock:
        # Only trigger on the first item in the queue
        has_ready = any(i.get("path") for i in response_queue)
    if not triggers_enabled or not has_ready:
        return
    if any(word in text.lower() for word in trigger_words):
        if pending_fire_timer is None or not pending_fire_timer.is_alive():
            socketio.emit("trigger_countdown", {"delay": TRIGGER_DELAY})
            pending_fire_timer = threading.Timer(TRIGGER_DELAY, auto_fire)
            pending_fire_timer.start()


def auto_fire():
    global pending_fire_timer
    pending_fire_timer = None
    with queue_lock:
        item = next((i for i in response_queue if i.get("path")), None)
    if item:
        socketio.emit("status", {"msg": "Auto-firing!", "state": "speaking"})
        threading.Thread(target=play_item, args=(item,), daemon=True).start()


def start_listener():
    asyncio.run(_listen_loop())


def generate_and_save(text: str, item_id: str) -> str:
    audio = eleven_client.text_to_speech.convert(
        text=text, voice_id=VOICE_ID, model_id="eleven_flash_v2_5"
    )
    path = f"output_{item_id}.mp3"
    with open(path, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    return path


def play_item(item: dict):
    """Play the audio for a queue item, then remove it from the queue."""
    global afplay_proc
    import subprocess

    with queue_lock:
        if item in response_queue:
            response_queue.remove(item)
    socketio.emit("queue_remove", {"id": item["id"]})

    afplay_proc = subprocess.Popen(["afplay", item["path"]])
    afplay_proc.wait()
    afplay_proc = None

    try:
        os.remove(item["path"])
    except OSError:
        pass

    with queue_lock:
        has_more = any(i.get("path") for i in response_queue)

    if has_more:
        socketio.emit("status", {"msg": "Ready — press Speak or wait for trigger", "state": "ready"})
    else:
        socketio.emit("status", {"msg": "Listening", "state": "listening"})
    socketio.emit("spoke", {})


@socketio.on("generate")
def handle_generate(data):
    text = data.get("text", "").strip()
    if not text:
        return
    item_id = str(uuid.uuid4())[:8]
    # Add card immediately in loading state
    socketio.emit("queue_add", {"id": item_id, "text": text, "loading": True})
    socketio.emit("status", {"msg": "Generating...", "state": "generating"})

    def do_generate():
        try:
            path = generate_and_save(text, item_id)
            item = {"id": item_id, "text": text, "path": path}
            with queue_lock:
                response_queue.append(item)
            socketio.emit("queue_ready", {"id": item_id})
            socketio.emit("status", {"msg": "Ready — press Speak or wait for trigger", "state": "ready"})
        except Exception as e:
            socketio.emit("queue_error", {"id": item_id, "error": str(e)})
            socketio.emit("status", {"msg": f"Error: {e}", "state": "error"})

    threading.Thread(target=do_generate, daemon=True).start()


@socketio.on("regenerate")
def handle_regenerate(data):
    """Re-generate audio for an existing queue item after text was edited."""
    item_id = data.get("id", "").strip()
    new_text = data.get("text", "").strip()
    if not item_id or not new_text:
        return

    with queue_lock:
        item = next((i for i in response_queue if i["id"] == item_id), None)
    if not item:
        return

    # Mark as loading in UI while re-generating
    socketio.emit("queue_add", {"id": item_id, "text": new_text, "loading": True})
    socketio.emit("status", {"msg": "Regenerating...", "state": "generating"})

    def do_regen():
        try:
            path = generate_and_save(new_text, item_id)
            with queue_lock:
                item["text"] = new_text
                item["path"] = path
            socketio.emit("queue_ready", {"id": item_id})
            socketio.emit("status", {"msg": "Ready — press Speak or wait for trigger", "state": "ready"})
        except Exception as e:
            socketio.emit("queue_error", {"id": item_id, "error": str(e)})
            socketio.emit("status", {"msg": f"Error: {e}", "state": "error"})

    threading.Thread(target=do_regen, daemon=True).start()


@socketio.on("speak")
def handle_speak(data=None):
    """Speak a specific item by id, or the first ready item if no id given."""
    global pending_fire_timer
    if pending_fire_timer:
        pending_fire_timer.cancel()
        pending_fire_timer = None

    item_id = (data or {}).get("id")
    with queue_lock:
        if item_id:
            item = next((i for i in response_queue if i["id"] == item_id and i.get("path")), None)
        else:
            item = next((i for i in response_queue if i.get("path")), None)

    if item:
        socketio.emit("status", {"msg": "Speaking...", "state": "speaking"})
        threading.Thread(target=play_item, args=(item,), daemon=True).start()


@socketio.on("remove")
def handle_remove(data):
    """Remove an item from the queue without speaking it."""
    item_id = data.get("id", "")
    with queue_lock:
        item = next((i for i in response_queue if i["id"] == item_id), None)
        if item:
            response_queue.remove(item)
    socketio.emit("queue_remove", {"id": item_id})
    with queue_lock:
        has_items = len(response_queue) > 0
    if not has_items:
        socketio.emit("status", {"msg": "Listening", "state": "listening"})


@socketio.on("stop")
def handle_stop():
    global afplay_proc, pending_fire_timer
    if pending_fire_timer:
        pending_fire_timer.cancel()
        pending_fire_timer = None
    if afplay_proc:
        afplay_proc.terminate()
        afplay_proc = None
    socketio.emit("status", {"msg": "Stopped", "state": "listening"})
    socketio.emit("spoke", {})


@socketio.on("update_triggers")
def handle_update_triggers(data):
    global trigger_words, triggers_enabled
    trigger_words = [w.strip().lower() for w in data.get("words", []) if w.strip()]
    triggers_enabled = data.get("enabled", True)


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    threading.Thread(target=start_listener, daemon=True).start()
    print("UNMUTE running at http://localhost:5001")
    socketio.run(app, host="0.0.0.0", port=5001, debug=False, allow_unsafe_werkzeug=True)