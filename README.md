# UNMUTE

A meeting voice proxy that gives everyone an equal voice in the room.

UNMUTE listens to your call, detects when you're being invited to speak, and delivers your thoughts at exactly the right moment — clearly, confidently, and on time. Built for anyone who has ever had something valuable to say but couldn't find the gap to say it.

---

## Who it's for

- People with social anxiety who struggle to interject in fast-moving conversations
- Non-native speakers who need a moment to compose their thoughts in a second language
- People with stutters or other speech differences who want to participate without pressure
- Anyone who thinks better in writing than on the spot

UNMUTE doesn't replace your voice. It gives it back to you.

---

## How it works

1. Type your thought into the web UI and press **Enter** — your response is prepared in the background while the conversation continues
2. When someone says a trigger phrase like *"any questions?"* or calls your name, UNMUTE detects it in real time and fires your response after a short pause
3. Press **▶ Speak** to jump in manually at any moment
4. Press **■ Stop** if you change your mind

---

## Setup

### 1. Install dependencies

```bash
pip install flask flask-socketio elevenlabs websockets sounddevice python-dotenv
brew install blackhole-2ch
```

### 2. Configure environment

Create a `.env` file in the project root:

```
ELEVEN_API_KEY=your_elevenlabs_api_key
```

Get your key at [elevenlabs.io](https://elevenlabs.io) — a free account is all you need.

### 3. Set up BlackHole (for capturing meeting audio)

BlackHole lets UNMUTE hear what other speakers are saying on your call.

1. Open **Audio MIDI Setup** (search in Spotlight)
2. Click **+** → **Create Multi-Output Device**
3. Check both **BlackHole 2ch** and your headphones/speakers
4. Go to **System Settings → Sound** and set output to the Multi-Output Device
5. In your meeting app (Zoom, Meet, etc.), set audio output to the same Multi-Output Device

Your meeting audio will now play through your ears and into UNMUTE simultaneously.

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
├── .env                # API keys
└── templates/
    └── index.html      # Web UI
```

---

## Features

- **Live transcript** — real-time speech-to-text via ElevenLabs Scribe v2, so you always know what's being said
- **Trigger words** — fully editable in the UI; auto-fires when a cue phrase is detected mid-speech
- **1 second delay** — a visible countdown gives you a moment to cancel before your response plays
- **Toggle on/off** — pause auto-firing instantly without losing your trigger word list
- **Manual speak** — take control and fire your response whenever feels right
- **Stop button** — cancel at any point, no questions asked

---

## Customisation

| Setting | Location | Default |
|---|---|---|
| Voice ID | `app.py` → `VOICE_ID` | ElevenLabs George |
| Trigger delay | `app.py` → `TRIGGER_DELAY` | `1.0` seconds |
| Trigger words | Web UI (editable live) | questions, thoughts, your name, add anything, feedback |
| Port | `app.py` → `socketio.run(...)` | `5001` |

---

## Requirements

- macOS
- Python 3.9+
- ElevenLabs account (free tier)
- BlackHole 2ch (free, open source)