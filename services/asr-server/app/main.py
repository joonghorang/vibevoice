from __future__ import annotations

import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models import AudioConfigRequest, SessionRequest
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


@app.post("/api/session/start")
async def start_session(request: SessionRequest):
    return await live_session.start_session(request.hotwords)


@app.post("/api/session/stop")
async def stop_session():
    return await live_session.stop_session()


@app.get("/api/session/export")
async def export_session():
    return live_session.snapshot


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    await live_session.connect(websocket)
    try:
        while True:
            message = await websocket.receive()
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
    except WebSocketDisconnect:
        await live_session.disconnect(websocket)
