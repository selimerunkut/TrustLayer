"""ElevenLabs text-to-speech and speech-to-text (REST, via httpx).

Credentials and defaults come from the environment — never hard-code API keys.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"

# Reasonable default for long broker replies (ElevenLabs has payload limits; trim for cost/latency).
_MAX_TTS_CHARS = 4_000


class ElevenLabsTTSHTTPError(RuntimeError):
    """Raised when ElevenLabs rejects a TTS request with an HTTP error."""

    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"ElevenLabs TTS failed ({status_code}): {detail}")


def elevenlabs_configured() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY", "").strip() and os.getenv("ELEVENLABS_VOICE_ID", "").strip())


def _tts_model_id() -> str:
    return os.getenv("ELEVENLABS_TTS_MODEL_ID", "eleven_turbo_v2_5").strip() or "eleven_turbo_v2_5"


def _tts_speed() -> float:
    """ElevenLabs ``voice_settings.speed`` (1.0 = normal).

    Many models only accept ``0.7``–``1.2`` (per API validation); values are clamped there.
    """
    raw = os.getenv("ELEVENLABS_TTS_SPEED", "1.1").strip()
    try:
        v = float(raw)
    except ValueError:
        v = 1.1
    return max(0.7, min(1.2, v))


def _voice_id() -> str:
    vid = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if not vid:
        raise RuntimeError("ELEVENLABS_VOICE_ID is not set (add it to your .env).")
    return vid


def _api_key() -> str:
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set (add it to your .env).")
    return key


def simplify_text_for_speech(text: str, *, max_chars: int = _MAX_TTS_CHARS) -> str:
    """Light cleanup so TTS does not read markdown markers aloud."""
    t = text.strip()
    t = re.sub(r"```[\s\S]*?```", " ", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"#+\s*", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > max_chars:
        t = t[: max_chars - 1].rstrip() + "…"
    return t


def synthesize_speech_mp3(
    text: str,
    *,
    api_key: str | None = None,
    voice_id: str | None = None,
    model_id: str | None = None,
    timeout_s: float = 120.0,
) -> bytes:
    """Return MP3 bytes for ``text`` (EU / US region: api.elevenlabs.io)."""
    key = api_key if api_key is not None else _api_key()
    vid = voice_id if voice_id is not None else _voice_id()
    mid = model_id if model_id is not None else _tts_model_id()
    clean = simplify_text_for_speech(text)
    if not clean:
        raise ValueError("Nothing left to speak after text cleanup.")

    url = TTS_URL.format(voice_id=vid)
    headers = {
        "xi-api-key": key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "text": clean,
        "model_id": mid,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "speed": _tts_speed(),
        },
    }

    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(url, headers=headers, json=body)
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        detail: Any = (r.text or "")[:500]
        try:
            payload = r.json()
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            detail = payload
        logger.warning("ElevenLabs TTS HTTP %s: %s", r.status_code, detail)
        raise ElevenLabsTTSHTTPError(r.status_code, detail) from e

    data = r.content
    if not data or len(data) < 100:
        raise RuntimeError("ElevenLabs TTS returned an empty or suspiciously short body.")
    return data


def transcribe_audio_bytes(
    audio_bytes: bytes,
    *,
    filename: str = "recording.webm",
    content_type: str = "audio/webm",
    api_key: str | None = None,
    model_id: str = "scribe_v2",
    timeout_s: float = 120.0,
) -> str:
    """Transcribe short microphone audio via ElevenLabs speech-to-text."""
    key = api_key if api_key is not None else _api_key()
    headers = {"xi-api-key": key}

    files = {"file": (filename, audio_bytes, content_type)}
    data = {"model_id": model_id}

    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(STT_URL, headers=headers, files=files, data=data)

    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        detail = (r.text or "")[:500]
        logger.warning("ElevenLabs STT HTTP %s: %s", r.status_code, detail)
        raise RuntimeError(f"ElevenLabs transcription failed ({r.status_code}): {detail}") from e

    try:
        payload: dict[str, Any] = r.json()
    except json.JSONDecodeError as e:
        raise RuntimeError("ElevenLabs STT returned non-JSON.") from e

    if isinstance(payload.get("text"), str) and payload["text"].strip():
        return payload["text"].strip()

    transcripts = payload.get("transcripts")
    if isinstance(transcripts, list):
        parts = []
        for item in transcripts:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"].strip())
        if parts:
            return " ".join(parts).strip()

    raise RuntimeError("ElevenLabs STT response had no transcript text.")
