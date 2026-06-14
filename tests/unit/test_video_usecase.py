"""Unit tests for video generation use case."""

from __future__ import annotations

import pytest

from services.ai_api.application.dto.video_request import VideoRequest
from services.ai_api.infrastructure.ai_models.video_generator import MockVideoGenerator


class TestVideoRequest:
    """Tests for VideoRequest DTO."""

    def test_default_config(self):
        req = VideoRequest(prompt="test")
        assert req.prompt == "test"
        assert req.width == 512
        assert req.height == 512

    def test_model_config_merge(self):
        req = VideoRequest(
            prompt="test",
            width=768,
            extra_config={"custom_param": True},
        )
        config = req.model_config
        assert config["width"] == 768
        assert config["custom_param"] is True

    def test_seed_optional(self):
        req = VideoRequest(prompt="test")
        assert req.seed is None
        config = req.model_config
        assert config["seed"] is None


class TestMockVideoGenerator:
    """Tests for MockVideoGenerator service."""

    @pytest.mark.asyncio
    async def test_is_ready(self):
        gen = MockVideoGenerator()
        assert await gen.is_ready() is True

    @pytest.mark.asyncio
    async def test_get_supported_config(self):
        gen = MockVideoGenerator()
        config = await gen.get_supported_config()
        assert "width" in config
        assert "height" in config
        assert "num_frames" in config

    @pytest.mark.asyncio
    async def test_generate_stream_yields_chunks(self):
        gen = MockVideoGenerator()
        chunks = []
        async for chunk in gen.generate_stream(
            prompt="test prompt",
            config={"num_frames": 4},
            job_id="test-job",
        ):
            chunks.append(chunk)

        assert len(chunks) == 4
        assert chunks[0].frame_idx == 0
        assert chunks[-1].is_final is True
        assert chunks[-1].frame_idx == 3

    @pytest.mark.asyncio
    async def test_generate_batch(self):
        gen = MockVideoGenerator()
        result = await gen.generate(
            prompt="test",
            config={"num_frames": 4, "width": 256},
            job_id="batch-job",
        )
        assert result.job_id == "batch-job"
        assert result.width == 256
        assert result.url is not None
