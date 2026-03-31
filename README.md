# VibeVoice Classroom

Local-first classroom captioning for mixed Korean and English lectures. The app listens to a classroom microphone, or processes a sample/uploaded WAV file, renders the original transcript on the left, renders the opposite-language translation on the right, and keeps the current utterance centered with auto-follow scrolling.

## What Is Included

- `apps/web`: React + Vite split-screen subtitle UI
- `services/asr-server`: FastAPI WebSocket server for microphone audio, ASR, and Google translation
- `data/sessions`: exported session snapshots
- `.models`: ignored local cache for pre-downloaded VibeVoice model files

## Architecture

1. The browser captures microphone audio with `AudioWorklet`.
2. Audio chunks are streamed to the local FastAPI server over WebSocket.
3. The server buffers the stream, runs rolling-window transcription, and merges utterances.
4. Each utterance is translated into the opposite language.
5. The UI receives live session snapshots and auto-scrolls to the active line.

When a microphone is not available, the web UI can also process the bundled sample WAV or an uploaded PCM WAV file through the same transcription and translation pipeline.

## Project Layout

```text
/Users/kimjoongil/vibevoice
  apps/web
  services/asr-server
  data/sessions
```

## Setup

### 1. Frontend dependencies

```bash
npm install
```

### 2. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/asr-server/requirements.txt
```

### 3. Pre-download the VibeVoice models locally

This project is set up to reuse a local Hugging Face cache under `.models/` instead of downloading on every restart.

```bash
npm run download:models
```

The server will then load from the local cache only.

### 4. Environment variables

Copy [.env.example](/Users/kimjoongil/vibevoice/.env.example) to `.env` and update:

- `GOOGLE_CLOUD_PROJECT`: your Google Cloud project id
- `GOOGLE_APPLICATION_CREDENTIALS`: absolute path to your service-account key
- `TRANSCRIPTION_PROVIDER=mock` for UI development
- `TRANSCRIPTION_PROVIDER=vibevoice` for real transcription with `microsoft/VibeVoice-ASR-HF`
- `VIBEVOICE_CACHE_DIR=./.models/huggingface` keeps the downloaded model cache inside the repo but ignored by git
- `VIBEVOICE_LOCAL_FILES_ONLY=true` makes runtime fail fast instead of downloading from the network

### 5. Run

Frontend and backend in separate terminals:

```bash
npm run dev:web
```

```bash
python3 -m uvicorn app.main:app --reload --app-dir services/asr-server --host 127.0.0.1 --port 8000
```

Or use the combined script after frontend dependencies are installed:

```bash
npm run dev
```

## Notes On Providers

- `VibeVoice Realtime` is a text-to-speech model, so this project uses `VibeVoice ASR` instead for transcription.
- Google Cloud Translation Advanced v3 is used from the local backend so API credentials stay out of the browser.
- The default `mock` transcription mode keeps the UI testable before the heavyweight ASR stack is installed.
- In `vibevoice` mode the server expects the model to already exist in `.models/` and uses local files only.
- The repo includes [data/samples/vibevoice-example-output.wav](/Users/kimjoongil/vibevoice/data/samples/vibevoice-example-output.wav) for microphone-free testing.

## Recommended Next Steps

1. Install the Python dependencies in a local virtual environment.
2. Switch `TRANSCRIPTION_PROVIDER` from `mock` to `vibevoice`.
3. Add a lecture-specific glossary in Google Cloud Translation for course terminology.
4. Test with a 3 to 5 minute bilingual lecture recording before live classroom use.
