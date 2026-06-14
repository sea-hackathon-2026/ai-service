"""Unit tests for TTS use case."""

from __future__ import annotations

import pytest

from services.ai_api.application.dto.tts_request import TTSRequest
from services.ai_api.infrastructure.ai_models.tts_engine import MockTTSEngine


class TestTTSRequest:
    """Tests for TTSRequest DTO."""

    def test_defaults(self):
        req = TTSRequest(text="hello world")
        assert req.text == "hello world"
        assert req.voice == "default"
        assert req.language == "vi"
        assert req.audio_format == "wav"
        assert req.speed == 1.0

    def test_custom_params(self):
        req = TTSRequest(
            text="test",
            voice="vi-female-01",
            language="vi",
            audio_format="mp3",
            speed=1.5,
        )
        assert req.voice == "vi-female-01"
        assert req.audio_format == "mp3"
        assert req.speed == 1.5


class TestMockTTSEngine:
    """Tests for MockTTSEngine service."""

    @pytest.mark.asyncio
    async def test_is_ready(self):
        engine = MockTTSEngine()
        assert await engine.is_ready() is True

    @pytest.mark.asyncio
    async def test_list_voices(self):
        engine = MockTTSEngine()
        voices = await engine.list_voices()
        assert len(voices) > 0
        assert all("id" in v for v in voices)

    @pytest.mark.asyncio
    async def test_synthesize_stream_yields_chunks(self):
        engine = MockTTSEngine()
        chunks = []
        async for chunk in engine.synthesize_stream(
            text="Xin chào, đây là bài test.",
            voice="vi-female-01",
            audio_format="wav",
            job_id="tts-test",
        ):
            chunks.append(chunk)

        assert len(chunks) > 0
        assert chunks[-1].is_final is True
        assert all(c.sample_rate == 22050 for c in chunks)

    @pytest.mark.asyncio
    async def test_synthesize_batch(self):
        engine = MockTTSEngine()
        result = await engine.synthesize(
            text="Hello world",
            voice="en-female-01",
            audio_format="wav",
            job_id="tts-batch",
        )
        assert result.job_id == "tts-batch"
        assert result.format == "wav"
        assert result.url is not None

    @pytest.mark.asyncio
    async def test_long_text_multiple_chunks(self):
        """Long text should produce multiple audio chunks."""
        engine = MockTTSEngine()
        long_text = "A" * 200  # Should produce ~4 chunks (50 chars each)
        chunks = []
        async for chunk in engine.synthesize_stream(
            text=long_text,
            voice="default",
            audio_format="wav",
            job_id="long-test",
        ):
            chunks.append(chunk)

        assert len(chunks) == 4
        assert chunks[-1].is_final is True
