from __future__ import annotations

import base64
import logging

import httpx

from .core import Settings
from .privacy import mask_phi

logger = logging.getLogger(__name__)

ALLOWED_MIME = {
    "audio/webm",
    "audio/webm;codecs=opus",
    "audio/ogg",
    "audio/ogg;codecs=opus",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp3",
}


async def transcribe_with_gemini(
    settings: Settings,
    audio: bytes,
    mime_type: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required for voice transcription")
    if len(audio) > 8_000_000:
        raise ValueError("Audio upload is too large (max 8MB)")
    normalized = (mime_type or "audio/webm").split(";")[0].strip().lower()
    if normalized not in {item.split(";")[0] for item in ALLOWED_MIME} and not normalized.startswith("audio/"):
        raise ValueError("Unsupported audio type")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    prompt = (
        "Transcribe the patient's spoken symptom report into plain English text only. "
        "Do not diagnose, prescribe, or add medical advice. "
        "Return only the transcript words the speaker said."
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": normalized if normalized.startswith("audio/") else "audio/webm",
                            "data": base64.b64encode(audio).decode("ascii"),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {"temperature": 0},
    }
    async with httpx.AsyncClient(timeout=60.0, transport=transport) as client:
        response = await client.post(url, params={"key": settings.gemini_api_key}, json=payload)
        response.raise_for_status()
        body = response.json()
    try:
        text = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("Unexpected Gemini transcription payload")
        raise RuntimeError("Transcription provider returned an empty result") from exc
    transcript = " ".join(str(text).split()).strip()
    if not transcript:
        raise RuntimeError("No speech detected in the recording")
    return mask_phi(transcript)
