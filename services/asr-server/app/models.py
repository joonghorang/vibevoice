from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UtteranceModel(BaseModel):
    id: str
    speaker: str
    start_ms: int
    end_ms: int
    source_lang: Literal["ko", "en"]
    source_text: str
    translated_text: str = ""
    status: Literal["partial", "final"]
    translated_from_text: str = ""


class SessionSnapshot(BaseModel):
    session_id: str | None = None
    status: Literal["idle", "listening", "processing", "stopped"] = "idle"
    started_at: datetime | None = None
    updated_at: datetime | None = None
    audio_level: float = 0.0
    active_utterance_id: str | None = None
    transcription_provider: str
    translation_provider: str
    hotwords: list[str] = Field(default_factory=list)
    utterances: list[UtteranceModel] = Field(default_factory=list)
    last_error: str | None = None


class SessionRequest(BaseModel):
    hotwords: list[str] = Field(default_factory=list)


class SampleFileInfo(BaseModel):
    name: str
    size_bytes: int


class SampleProcessRequest(BaseModel):
    sample_name: str
    hotwords: list[str] = Field(default_factory=list)


class AudioConfigRequest(BaseModel):
    sampleRate: int


class EventEnvelope(BaseModel):
    type: str
    payload: SessionSnapshot
