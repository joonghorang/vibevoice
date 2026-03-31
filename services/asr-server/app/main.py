from __future__ import annotations

import io
import json
import wave

import numpy as np

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models import (
    AudioConfigRequest,
    SampleFileInfo,
    SampleProcessRequest,
    SessionRequest,
)
from .session import LiveSessionService
from .transcriber import build_transcription_service
from .translation import build_translation_service

app = FastAPI(title="VibeVoice Classroom Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

live_session = LiveSessionService(
    settings=settings,
    transcriber=build_transcription_service(settings),
    translator=build_translation_service(settings),
)


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "ok": True,
        "transcription_provider": live_session.snapshot.transcription_provider,
        "translation_provider": live_session.snapshot.translation_provider,
    }


@app.get("/api/session/current")
async def get_current_session():
    return live_session.snapshot


@app.get("/api/samples")
async def list_samples() -> list[SampleFileInfo]:
    return [
        SampleFileInfo(name=path.name, size_bytes=path.stat().st_size)
        for path in sorted(settings.samples_dir.glob("*.wav"))
    ]


@app.post("/api/session/start")
async def start_session(request: SessionRequest):
    return await live_session.start_session(request.hotwords)


@app.post("/api/session/stop")
async def stop_session():
    return await live_session.stop_session()


@app.get("/api/session/export")
async def export_session():
    return live_session.snapshot


@app.post("/api/session/process-sample")
async def process_sample(request: SampleProcessRequest):
    sample_path = settings.samples_dir / request.sample_name
    if not sample_path.is_file():
        raise HTTPException(status_code=404, detail="Sample not found.")

    audio, sample_rate = load_wav_audio(sample_path.read_bytes(), sample_path.name)
    return await live_session.process_audio_file(
        audio=audio,
        sample_rate=sample_rate,
        hotwords=request.hotwords,
        source_name=sample_path.name,
    )


@app.post("/api/session/upload")
async def upload_audio(
    file: UploadFile = File(...),
    hotwords: str = Form(default=""),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name.")

    content = await file.read()
    hotword_list = [item.strip() for item in hotwords.split(",") if item.strip()]
    audio, sample_rate = load_wav_audio(content, file.filename)
    return await live_session.process_audio_file(
        audio=audio,
        sample_rate=sample_rate,
        hotwords=hotword_list,
        source_name=file.filename,
    )


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    await live_session.connect(websocket)
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            if message.get("bytes") is not None:
                await live_session.receive_audio(message["bytes"])
                continue

            raw_text = message.get("text")
            if not raw_text:
                continue

            payload = json.loads(raw_text)
            event_type = payload.get("type")

            if event_type == "audio.config":
                config = AudioConfigRequest(**payload.get("payload", {}))
                await live_session.configure_audio(config.sampleRate)
    except RuntimeError:
        pass
    except WebSocketDisconnect:
        pass
    finally:
        await live_session.disconnect(websocket)


def load_wav_audio(content: bytes, source_name: str) -> tuple[np.ndarray, int]:
    try:
        with wave.open(io.BytesIO(content), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            sample_width = wav_file.getsampwidth()
            channel_count = wav_file.getnchannels()
            frame_count = wav_file.getnframes()
            raw_frames = wav_file.readframes(frame_count)
    except wave.Error as error:
        raise HTTPException(
            status_code=400,
            detail=f"{source_name} must be a PCM WAV file.",
        ) from error

    if sample_width == 1:
        audio = (
            np.frombuffer(raw_frames, dtype=np.uint8).astype(np.float32) - 128.0
        ) / 128.0
    elif sample_width == 2:
        audio = np.frombuffer(raw_frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 4:
        audio = np.frombuffer(raw_frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise HTTPException(
            status_code=400,
            detail=f"{source_name} uses unsupported sample width {sample_width}.",
        )

    if channel_count > 1:
        audio = audio.reshape(-1, channel_count).mean(axis=1)

    return audio.astype(np.float32, copy=False), sample_rate
