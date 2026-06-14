"""Integration tests for REST API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Test health check endpoints."""

    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_readiness(self, client: AsyncClient):
        response = await client.get("/readiness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ready", "degraded")
        assert "services" in data


class TestVideoEndpoints:
    """Test video generation REST endpoints."""

    @pytest.mark.asyncio
    async def test_get_video_config(self, client: AsyncClient):
        response = await client.get("/v1/video/config")
        assert response.status_code == 200
        data = response.json()
        assert "config" in data

    @pytest.mark.asyncio
    async def test_generate_video_requires_auth(self, client: AsyncClient):
        response = await client.post(
            "/v1/video/generate",
            json={"prompt": "test"},
        )
        # Should fail without API key
        assert response.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_generate_video_with_auth(self, client: AsyncClient, api_key_header: dict):
        response = await client.post(
            "/v1/video/generate",
            json={"prompt": "A cat walking in the park"},
            headers=api_key_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "done"


class TestTTSEndpoints:
    """Test TTS REST endpoints."""

    @pytest.mark.asyncio
    async def test_list_voices(self, client: AsyncClient):
        response = await client.get("/v1/tts/voices")
        assert response.status_code == 200
        data = response.json()
        assert "voices" in data
        assert len(data["voices"]) > 0

    @pytest.mark.asyncio
    async def test_synthesize_with_auth(self, client: AsyncClient, api_key_header: dict):
        response = await client.post(
            "/v1/tts/synthesize",
            json={"text": "Xin chào Việt Nam", "voice": "vi-female-01"},
            headers=api_key_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "done"
