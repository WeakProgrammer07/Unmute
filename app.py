import os
import json
import base64
import asyncio
import threading
import time
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
TRIGGER_DELAY = 1.0 # seconds before auto-firing

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

trigger_words = ["questions", "thoughts", "liam", "add anything", "feedback"]
triggers_enabled = True
trigger_detected = threading.Event()
pending_path = None
afplay_proc = None         # Current afplay process so we can kill it
pending_fire_timer = None  # Timer for the 1s delay

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
    if not triggers_enabled or not pending_path:
        return
    if any(word in text.lower() for word in trigger_words):
        if pending_fire_timer is None or not pending_fire_timer.is_alive():
            socketio.emit("trigger_countdown", {"delay": TRIGGER_DELAY})
            pending_fire_timer = threading.Timer(TRIGGER_DELAY, auto_fire)
            pending_fire_timer.start()

def auto_fire():
    global pending_path, pending_fire_timer
    pending_fire_timer = None
    if pending_path:
        socketio.emit("status", {"msg": "Auto-firing!", "state": "speaking"})
        path = pending_path
        pending_path = None
        threading.Thread(target=play_audio, args=(path,), daemon=True).start()

def start_listener():
    asyncio.run(_listen_loop())

def generate_and_save(text: str) -> str:
    audio = eleven_client.text_to_speech.convert(
        text=text, voice_id=VOICE_ID, model_id="eleven_flash_v2_5"
    )
    path = "output.mp3"
    with open(path, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    return path

def play_audio(path: str):
    global afplay_proc
    afplay_proc = __import__("subprocess").Popen(["afplay", path])
    afplay_proc.wait()
    afplay_proc = None
    socketio.emit("status", {"msg": "Listening", "state": "listening"})
    socketio.emit("spoke", {})

@socketio.on("generate")
def handle_generate(data):
    global pending_path
    text = data.get("text", "").strip()
    if not text:
        return
    socketio.emit("status", {"msg": "Generating...", "state": "generating"})
    try:
        pending_path = generate_and_save(text)
        socketio.emit("ready", {"text": text})
        socketio.emit("status", {"msg": "Ready — press Speak or wait for trigger", "state": "ready"})
    except Exception as e:
        socketio.emit("status", {"msg": f"Error: {e}", "state": "error"})

@socketio.on("speak")
def handle_speak():
    global pending_path, pending_fire_timer
    if pending_fire_timer:
        pending_fire_timer.cancel()
        pending_fire_timer = None
    if pending_path:
        socketio.emit("status", {"msg": "Speaking...", "state": "speaking"})
        path = pending_path
        pending_path = None
        threading.Thread(target=play_audio, args=(path,), daemon=True).start()

@socketio.on("stop")
def handle_stop():
    global afplay_proc, pending_path, pending_fire_timer
    # Cancel pending timer
    if pending_fire_timer:
        pending_fire_timer.cancel()
        pending_fire_timer = None
    # Kill active playback
    if afplay_proc:
        afplay_proc.terminate()
        afplay_proc = None
    pending_path = None
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
    print("=== UNMUTE running at http://localhost:5001 ===")
    socketio.run(app, host="0.0.0.0", port=5001, debug=False, allow_unsafe_werkzeug=True)