"""API docs endpoints are gated by ENABLE_API_DOCS."""

from __future__ import annotations

import httpx

from backend.application.api.main import create_app
from backend.config import Settings
from support.test_container import build_test_container


async def test_docs_disabled_by_default() -> None:
    container = build_test_container()
    app = create_app(settings=container.settings, container=container)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/redoc")).status_code == 404
        assert (await client.get("/openapi.json")).status_code == 404


async def test_docs_enabled_when_configured() -> None:
    settings = Settings(enable_api_docs=True, relevance_threshold=0.0, retrieval_top_k=8)
    container = build_test_container(settings=settings)
    app = create_app(settings=container.settings, container=container)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        assert (await client.get("/docs")).status_code == 200
        assert (await client.get("/redoc")).status_code == 200
        openapi = await client.get("/openapi.json")
        assert openapi.status_code == 200
        assert openapi.json()["info"]["title"] == "Audit Assistant API"
