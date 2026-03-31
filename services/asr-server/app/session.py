from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
from fastapi import WebSocket

from .config import Settings
from .models import EventEnvelope, SessionSnapshot, UtteranceModel
from .transcriber import DraftUtterance, TranscriptionService
from .translation import TranslationService, detect_language


class LiveSessionService:
    def __init__(
        self,
        settings: Settings,
        transcriber: TranscriptionService,
        translator: TranslationService,
    ) -> None:
        self._settings = settings
        self._transcriber = transcriber
        self._translator = translator
        self._clients: set[WebSocket] = set()
        self._snapshot = SessionSnapshot(
            transcription_provider=transcriber.provider_name,
            translation_provider=translator.provider_name,
        )
        self._buffer = np.array([], dtype=np.float32)
        self._buffer_lock = asyncio.Lock()
        self._sample_rate = settings.target_sample_rate
        self._process_task: asyncio.Task[None] | None = None
        self._last_processed_sample_count = 0

    @property
    def snapshot(self) -> SessionSnapshot:
        return self._snapshot

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)
        await self._send_snapshot(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def start_session(self, hotwords: list[str]) -> SessionSnapshot:
        if self._process_task:
            self._process_task.cancel()
            self._process_task = None

        self._buffer = np.array([], dtype=np.float32)
        self._last_processed_sample_count = 0
        now = datetime.utcnow()
        self._snapshot = SessionSnapshot(
            session_id=now.strftime("%Y%m%d-%H%M%S"),
            status="listening",
            started_at=now,
            updated_at=now,
            audio_level=0.0,
            active_utterance_id=None,
            transcription_provider=self._transcriber.provider_name,
            translation_provider=self._translator.provider_name,
            hotwords=hotwords,
            utterances=[],
            last_error=None,
        )
        self._process_task = asyncio.create_task(self._process_loop())
        await self._broadcast_snapshot()
        return self._snapshot

    async def stop_session(self) -> SessionSnapshot:
        if self._process_task:
            self._process_task.cancel()
            self._process_task = None

        self._snapshot.status = "stopped"
        self._snapshot.updated_at = datetime.utcnow()
        await self._persist_session()
        await self._broadcast_snapshot()
        return self._snapshot

    async def configure_audio(self, sample_rate: int) -> None:
        self._sample_rate = sample_rate

    async def receive_audio(self, chunk_bytes: bytes) -> None:
        if self._snapshot.status not in {"listening", "processing"}:
            return

        samples = np.frombuffer(chunk_bytes, dtype=np.float32)
        if samples.size == 0:
            return

        self._snapshot.audio_level = float(np.sqrt(np.mean(samples**2)))
        target_rate = self._settings.target_sample_rate
        if self._sample_rate != target_rate:
            samples = _resample_audio(samples, self._sample_rate, target_rate)

        async with self._buffer_lock:
            self._buffer = np.concatenate([self._buffer, samples])
            max_samples = int(target_rate * self._settings.rolling_window_seconds * 4)
            if len(self._buffer) > max_samples:
                self._buffer = self._buffer[-max_samples:]

    async def _process_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._settings.poll_interval_seconds)
                if self._snapshot.status == "stopped":
                    return

                audio_window, offset_ms, total_samples = await self._snapshot_window()
                if total_samples == self._last_processed_sample_count:
                    continue

                min_samples = int(
                    self._settings.min_buffer_seconds
                    * self._settings.target_sample_rate
                )
                if len(audio_window) < min_samples:
                    continue

                self._last_processed_sample_count = total_samples
                await self._run_inference(audio_window, offset_ms)
        except asyncio.CancelledError:
            return

    async def _snapshot_window(self) -> tuple[np.ndarray, int, int]:
        async with self._buffer_lock:
            total_samples = len(self._buffer)
            window_samples = int(
                self._settings.rolling_window_seconds * self._settings.target_sample_rate
            )
            audio_window = self._buffer[-window_samples:].copy()
            start_samples = max(total_samples - len(audio_window), 0)
            offset_ms = int(
                start_samples / self._settings.target_sample_rate * 1000
            )
            return audio_window, offset_ms, total_samples

    async def _run_inference(self, audio_window: np.ndarray, offset_ms: int) -> None:
        self._snapshot.status = "processing"
        self._snapshot.updated_at = datetime.utcnow()
        await self._broadcast_snapshot()

        try:
            prompt = ", ".join(self._snapshot.hotwords) if self._snapshot.hotwords else None
            drafts = await self._transcriber.transcribe(
                audio_window,
                self._settings.target_sample_rate,
                prompt,
            )
            await self._merge_drafts(drafts, offset_ms)
            await self._translate_utterances()
            self._snapshot.last_error = None
        except Exception as error:  # noqa: BLE001
            self._snapshot.last_error = str(error)
        finally:
            self._snapshot.status = "listening"
            self._snapshot.updated_at = datetime.utcnow()
            await self._broadcast_snapshot()

    async def _merge_drafts(
        self, drafts: list[DraftUtterance], offset_ms: int
    ) -> None:
        for draft in drafts:
            absolute_start = draft.start_ms + offset_ms
            absolute_end = draft.end_ms + offset_ms
            existing = self._find_matching_utterance(
                absolute_start, absolute_end, draft.speaker
            )

            if existing:
                if (
                    existing.source_text != draft.source_text
                    or existing.end_ms != absolute_end
                    or existing.status != draft.status
                ):
                    existing.source_text = draft.source_text
                    existing.end_ms = absolute_end
                    existing.status = draft.status
                    existing.source_lang = detect_language(draft.source_text)
                    existing.translated_text = ""
                    existing.translated_from_text = ""
                continue

            utterance = UtteranceModel(
                id=f"utt_{uuid.uuid4().hex[:8]}",
                speaker=draft.speaker,
                start_ms=absolute_start,
                end_ms=absolute_end,
                source_lang=detect_language(draft.source_text),
                source_text=draft.source_text,
                translated_text="",
                status=draft.status,
                translated_from_text="",
            )
            self._snapshot.utterances.append(utterance)

        self._snapshot.utterances.sort(key=lambda utterance: utterance.start_ms)
        self._snapshot.utterances = self._snapshot.utterances[-200:]
        self._snapshot.active_utterance_id = (
            self._snapshot.utterances[-1].id if self._snapshot.utterances else None
        )

    async def _translate_utterances(self) -> None:
        for utterance in self._snapshot.utterances:
            if (
                utterance.translated_text
                and utterance.translated_from_text == utterance.source_text
            ):
                continue

            translated = await self._translator.translate(
                utterance.source_text, utterance.source_lang
            )
            utterance.translated_text = translated
            utterance.translated_from_text = utterance.source_text

    def _find_matching_utterance(
        self, start_ms: int, end_ms: int, speaker: str
    ) -> UtteranceModel | None:
        for utterance in reversed(self._snapshot.utterances):
            if utterance.speaker != speaker:
                continue

            if abs(utterance.start_ms - start_ms) <= 1500 and abs(utterance.end_ms - end_ms) <= 3000:
                return utterance

        return None

    async def _broadcast_snapshot(self) -> None:
        disconnected: list[WebSocket] = []
        for client in self._clients:
            try:
                await self._send_snapshot(client)
            except Exception:  # noqa: BLE001
                disconnected.append(client)

        for client in disconnected:
            self._clients.discard(client)

    async def _send_snapshot(self, websocket: WebSocket) -> None:
        envelope = EventEnvelope(type="session.snapshot", payload=self._snapshot)
        await websocket.send_text(envelope.model_dump_json())

    async def _persist_session(self) -> None:
        if not self._snapshot.session_id:
            return

        output_path = self._settings.data_dir / f"{self._snapshot.session_id}.json"
        output_path.write_text(
            json.dumps(self._snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _resample_audio(
    samples: np.ndarray, source_rate: int, target_rate: int
) -> np.ndarray:
    if source_rate == target_rate or len(samples) == 0:
        return samples.astype(np.float32, copy=False)

    duration = len(samples) / source_rate
    target_length = max(int(duration * target_rate), 1)
    source_positions = np.linspace(0, len(samples) - 1, num=len(samples))
    target_positions = np.linspace(0, len(samples) - 1, num=target_length)
    resampled = np.interp(target_positions, source_positions, samples)
    return resampled.astype(np.float32)
