from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

import numpy as np

from .config import Settings
from .translation import detect_language


@dataclass
class DraftUtterance:
    speaker: str
    start_ms: int
    end_ms: int
    source_lang: str
    source_text: str
    status: str


class TranscriptionService:
    provider_name = "mock"

    async def transcribe(
        self, audio: np.ndarray, sample_rate: int, prompt: str | None
    ) -> list[DraftUtterance]:
        raise NotImplementedError


class MockTranscriptionService(TranscriptionService):
    provider_name = "mock"

    async def transcribe(
        self, audio: np.ndarray, sample_rate: int, prompt: str | None
    ) -> list[DraftUtterance]:
        duration_ms = int((len(audio) / sample_rate) * 1000)
        if duration_ms < 2500:
            return []

        text = (
            "Mock mode is active. Set TRANSCRIPTION_PROVIDER=vibevoice and install "
            "the server dependencies to enable live classroom transcription."
        )
        return [
            DraftUtterance(
                speaker="Speaker 1",
                start_ms=max(duration_ms - 2800, 0),
                end_ms=duration_ms,
                source_lang=detect_language(text),
                source_text=text,
                status="partial",
            )
        ]


class VibeVoiceTranscriptionService(TranscriptionService):
    provider_name = "vibevoice"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._processor = None
        self._model = None

    async def transcribe(
        self, audio: np.ndarray, sample_rate: int, prompt: str | None
    ) -> list[DraftUtterance]:
        return await asyncio.to_thread(self._transcribe_blocking, audio, sample_rate, prompt)

    def _load(self) -> None:
        if self._processor is not None and self._model is not None:
            return

        from transformers import AutoProcessor, VibeVoiceAsrForConditionalGeneration

        self._processor = AutoProcessor.from_pretrained(self._settings.vibevoice_model_id)
        self._model = VibeVoiceAsrForConditionalGeneration.from_pretrained(
            self._settings.vibevoice_model_id,
            device_map="auto",
        )

    def _transcribe_blocking(
        self, audio: np.ndarray, sample_rate: int, prompt: str | None
    ) -> list[DraftUtterance]:
        self._load()
        assert self._processor is not None
        assert self._model is not None

        audio = np.asarray(audio, dtype=np.float32)
        kwargs: dict[str, Any] = {
            "prompt": prompt or None,
            "sampling_rate": sample_rate,
        }
        inputs = self._processor.apply_transcription_request(audio, **kwargs).to(
            self._model.device, self._model.dtype
        )
        output_ids = self._model.generate(
            **inputs,
            acoustic_tokenizer_chunk_size=self._settings.vibevoice_chunk_size,
        )
        generated_ids = output_ids[:, inputs["input_ids"].shape[1] :]
        parsed = self._processor.decode(generated_ids, return_format="parsed")[0]

        if isinstance(parsed, str):
            parsed = _parse_json_like_string(parsed)

        drafts: list[DraftUtterance] = []
        for index, item in enumerate(parsed or []):
            text = str(item.get("Content") or item.get("content") or "").strip()
            if not text:
                continue

            start_sec = float(item.get("Start") or item.get("start") or 0.0)
            end_sec = float(item.get("End") or item.get("end") or start_sec)
            speaker_id = item.get("Speaker") or item.get("speaker") or 0
            drafts.append(
                DraftUtterance(
                    speaker=f"Speaker {speaker_id}",
                    start_ms=int(start_sec * 1000),
                    end_ms=int(end_sec * 1000),
                    source_lang=detect_language(text),
                    source_text=text,
                    status="final" if index < len(parsed) - 1 else "partial",
                )
            )

        return drafts


def _parse_json_like_string(value: str) -> list[dict[str, Any]]:
    match = re.search(r"(\[[\s\S]*\])", value)
    if not match:
        return []

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return []


def build_transcription_service(settings: Settings) -> TranscriptionService:
    if settings.transcription_provider.lower() == "vibevoice":
        return VibeVoiceTranscriptionService(settings)
    return MockTranscriptionService()
