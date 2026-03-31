from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    cors_origins: list[str]
    data_dir: Path
    transcription_provider: str
    vibevoice_model_id: str
    vibevoice_chunk_size: int
    target_sample_rate: int
    min_buffer_seconds: float
    rolling_window_seconds: float
    poll_interval_seconds: float
    google_project_id: str | None
    google_translate_location: str
    google_translate_glossary: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = ROOT_DIR / "data" / "sessions"
        data_dir.mkdir(parents=True, exist_ok=True)

        cors_origins = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://127.0.0.1:5173,http://localhost:5173",
            ).split(",")
            if origin.strip()
        ]

        return cls(
            host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "8000")),
            cors_origins=cors_origins,
            data_dir=data_dir,
            transcription_provider=os.getenv("TRANSCRIPTION_PROVIDER", "mock"),
            vibevoice_model_id=os.getenv(
                "VIBEVOICE_MODEL_ID", "microsoft/VibeVoice-ASR-HF"
            ),
            vibevoice_chunk_size=int(os.getenv("VIBEVOICE_CHUNK_SIZE", "1440000")),
            target_sample_rate=int(os.getenv("TARGET_SAMPLE_RATE", "24000")),
            min_buffer_seconds=float(os.getenv("MIN_BUFFER_SECONDS", "4")),
            rolling_window_seconds=float(os.getenv("ROLLING_WINDOW_SECONDS", "12")),
            poll_interval_seconds=float(os.getenv("POLL_INTERVAL_SECONDS", "2")),
            google_project_id=os.getenv("GOOGLE_CLOUD_PROJECT"),
            google_translate_location=os.getenv("GOOGLE_TRANSLATE_LOCATION", "global"),
            google_translate_glossary=os.getenv("GOOGLE_TRANSLATE_GLOSSARY") or None,
        )


settings = Settings.from_env()
