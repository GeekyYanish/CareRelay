from __future__ import annotations

import httpx
import pytest

from app.core import Settings
from app.transcribe import transcribe_with_gemini


@pytest.mark.asyncio
async def test_transcribe_with_gemini_returns_text():
    settings = Settings(gemini_api_key="test-key", gemini_model="gemini-flash-latest")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("key") == "test-key"
        assert b"inline_data" in request.content
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "  mild headache for two days  "}]}}]},
        )

    text = await transcribe_with_gemini(
        settings,
        b"fake-audio-bytes",
        "audio/webm",
        transport=httpx.MockTransport(handler),
    )
    assert text == "mild headache for two days"


@pytest.mark.asyncio
async def test_transcribe_requires_api_key():
    settings = Settings(gemini_api_key="")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        await transcribe_with_gemini(settings, b"x", "audio/webm")
