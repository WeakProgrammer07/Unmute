# UNMUTE

A meeting voice proxy that listens to your call, detects social cues, and speaks your pre-queued thoughts out loud at the right moment — using ElevenLabs for both speech-to-text and text-to-speech.

---

## How it works

1. Type a thought into the web UI and press **Enter** to generate the audio
2. When someone says a trigger word ("any questions?", "any thoughts?", etc.), UNMUTE waits 1 second then auto-fires your response
3. Or press **▶ Speak** manually whenever you're ready
4. Press **■ Stop** to cancel at any point

---

## Setup

### 1. Install dependencies

```bash
pip install flask flask-socketio elevenlabs websockets sounddevice python-dotenv
brew install blackhole-2ch   # For capturing meeting audio
```

### 2. Configure environment

Create a `.env` file in the project root:

```
ELEVEN_API_KEY=your_elevenlabs_api_key
```

Get your key at [elevenlabs.io](https://elevenlabs.io) — free tier works fine.

### 3. Set up BlackHole (for capturing meeting audio)

BlackHole lets UNMUTE hear what other speakers are saying on your call.

1. Open **Audio MIDI Setup** (search in Spotlight)
2. Click **+** → **Create Multi-Output Device**
3. Check both **BlackHole 2ch** and your headphones/speakers
4. Go to **System Settings → Sound** and set output to the Multi-Output Device
5. In your meeting app (Zoom, Meet, etc.), set audio output to the same Multi-Output Device

Your meeting audio will now play through your ears AND into UNMUTE simultaneously.

### 4. Run

```bash
python app.py
```

Open **http://127.0.0.1:5001** in your browser.

---

## Project structure

```
project/
├── app.py              # Flask backend, STT listener, TTS generation
├── .env                # API keys (never commit this)
└── templates/
    └── index.html      # Web UI
```

---

## Features

- **Live transcript** — real-time speech-to-text via ElevenLabs Scribe v2
- **Trigger words** — editable in the UI, auto-fires when detected mid-speech
- **1 second delay** — countdown bar gives you time to cancel before it fires
- **Toggle on/off** — disable auto-firing without removing your trigger words
- **Manual speak** — fire your queued thought at any time
- **Stop button** — cancels a pending countdown or kills audio mid-playback

---

## Customisation

| Setting | Location | Default |
|---|---|---|
| Voice ID | `app.py` → `VOICE_ID` | ElevenLabs George |
| Trigger delay | `app.py` → `TRIGGER_DELAY` | `1.0` seconds |
| Trigger words | Web UI (editable live) | questions, thoughts, liam, add anything, feedback |
| Port | `app.py` → `socketio.run(...)` | `5001` |

---

## Troubleshooting

**Port 5001 in use** — change the port in `app.py` or kill the existing process with `lsof -ti:5001 | xargs kill`

**No transcript appearing** — check that BlackHole is set up correctly, or switch your system mic to default and speak directly

**Audio not playing** — UNMUTE uses `afplay` (macOS built-in). Make sure your system volume is up and the correct output device is selected

**"Address already in use" on port 5000** — macOS AirPlay Receiver uses port 5000. Disable it in System Settings → General → AirDrop & Handoff, or just use port 5001

---

## Requirements

- macOS (uses `afplay` for audio playback)
- Python 3.9+
- ElevenLabs account (free tier)
- BlackHole 2ch (free, open source)
