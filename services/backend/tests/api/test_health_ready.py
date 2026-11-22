"""API test: readiness aggregates dependency failures."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import httpx

from backend.api.main import create_app
from support.fakes import FakeEmbedder
from support.test_container import build_test_container


class _FailingEmbedder(FakeEmbedder):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        _ = texts
        raise ConnectionError("ollama down")


async def test_ready_reports_embedding_failure() -> None:
    container = build_test_container(embedder=_FailingEmbedder())

    @asynccontextmanager
    async def session_factory() -> AsyncIterator[Any]:
        session = AsyncMock()
        session.execute = AsyncMock(return_value=None)
        yield session

    object.__setattr__(container, "session_factory", session_factory)

    app = create_app(settings=container.settings, container=container)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["postgres"]["ok"] is True
    assert body["checks"]["embeddings"]["ok"] is False
