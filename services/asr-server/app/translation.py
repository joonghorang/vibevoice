from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import httpx

from .config import Settings

LanguageCode = Literal["ko", "en"]


def detect_language(text: str) -> LanguageCode:
    hangul_count = sum(1 for char in text if "\uac00" <= char <= "\ud7a3")
    latin_count = sum(1 for char in text if char.isascii() and char.isalpha())
    return "ko" if hangul_count >= latin_count else "en"


class TranslationService:
    provider_name = "noop"

    async def translate(self, text: str, source_lang: LanguageCode) -> str:
        return text


class NoopTranslationService(TranslationService):
    provider_name = "noop"


@dataclass
class _AccessToken:
    token: str
    expires_at: datetime


class GoogleCloudTranslationService(TranslationService):
    provider_name = "google-cloud-v3"

    def __init__(self, settings: Settings) -> None:
        self._project_id = settings.google_project_id
        self._location = settings.google_translate_location
        self._glossary = settings.google_translate_glossary
        self._token_cache: _AccessToken | None = None

    async def translate(self, text: str, source_lang: LanguageCode) -> str:
        if not self._project_id:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is required for Google translation.")

        target_lang: LanguageCode = "en" if source_lang == "ko" else "ko"
        token = await asyncio.to_thread(self._get_access_token)

        url = (
            "https://translation.googleapis.com/v3/projects/"
            f"{self._project_id}/locations/{self._location}:translateText"
        )

        body: dict[str, object] = {
            "contents": [text],
            "mimeType": "text/plain",
            "sourceLanguageCode": source_lang,
            "targetLanguageCode": target_lang,
        }

        if self._glossary:
            body["glossaryConfig"] = {"glossary": self._glossary}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
            payload = response.json()

        translations = payload.get("translations") or []
        if not translations:
            return text

        return translations[0].get("translatedText", text)

    def _get_access_token(self) -> str:
        if self._token_cache and self._token_cache.expires_at > datetime.utcnow() + timedelta(minutes=1):
            return self._token_cache.token

        from google.auth import default
        from google.auth.transport.requests import Request

        credentials, _ = default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(Request())
        token = credentials.token
        if not token:
            raise RuntimeError("Unable to acquire Google Cloud access token.")

        expiry = credentials.expiry or (datetime.utcnow() + timedelta(minutes=30))
        self._token_cache = _AccessToken(token=token, expires_at=expiry)
        return token


def build_translation_service(settings: Settings) -> TranslationService:
    if settings.google_project_id:
        return GoogleCloudTranslationService(settings)
    return NoopTranslationService()
