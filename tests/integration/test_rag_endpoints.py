"""HTTP integration tests for retrieval without external model calls."""

import pytest
from httpx import ASGITransport, AsyncClient

from services.rag_service.main import app


@pytest.mark.asyncio
async def test_rag_health() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://rag-test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "rag-service"


@pytest.mark.asyncio
async def test_retrieval_returns_explainable_tags() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://rag-test") as client:
        response = await client.post(
            "/v1/retrieval/search",
            json={"query": "gia livestream khuyen mai", "top_k": 3},
        )

    assert response.status_code == 200
    documents = response.json()
    assert documents
    assert all(document["tag"] for document in documents)
