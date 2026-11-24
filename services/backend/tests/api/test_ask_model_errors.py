"""API test: model timeout/unavailable map to Problem Details."""

from __future__ import annotations

from backend.domain.engagement import EngagementId
from backend.domain.errors import (
    ContextTooLargeError,
    ModelTimeoutError,
    ModelUnavailableError,
)
from support.ask_api import (
    build_ask_app,
    index_chunk,
    post_ask,
    seed_engagement,
)
from support.fakes import (
    FakeChatModel,
    FakeEmbedder,
    InMemoryEngagementRepository,
    InMemoryVectorIndex,
)


async def test_model_timeout_returns_504() -> None:
    engagement_id: EngagementId = "northwind-fy2025"
    engagements = InMemoryEngagementRepository()
    await seed_engagement(engagements, engagement_id)
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await index_chunk(
        vector_index,
        embedder,
        engagement_id=engagement_id,
        path="contracts/a.md",
        text="Payment terms are Net-30.",
    )
    app = build_ask_app(
        engagements=engagements,
        vector_index=vector_index,
        embedder=embedder,
        chat=FakeChatModel(error=ModelTimeoutError("timed out")),
    )
    response = await post_ask(app, engagement_id, {"question": "What are payment terms?"})
    assert response.status_code == 504
    body = response.json()
    assert body["code"] == "model_timeout"


async def test_model_unavailable_returns_502() -> None:
    engagement_id: EngagementId = "northwind-fy2025"
    engagements = InMemoryEngagementRepository()
    await seed_engagement(engagements, engagement_id)
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await index_chunk(
        vector_index,
        embedder,
        engagement_id=engagement_id,
        path="contracts/a.md",
        text="Payment terms are Net-30.",
    )
    app = build_ask_app(
        engagements=engagements,
        vector_index=vector_index,
        embedder=embedder,
        chat=FakeChatModel(error=ModelUnavailableError("down")),
    )
    response = await post_ask(app, engagement_id, {"question": "What are payment terms?"})
    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "model_unavailable"


async def test_context_too_large_returns_413() -> None:
    engagement_id: EngagementId = "northwind-fy2025"
    engagements = InMemoryEngagementRepository()
    await seed_engagement(engagements, engagement_id)
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await index_chunk(
        vector_index,
        embedder,
        engagement_id=engagement_id,
        path="contracts/a.md",
        text="Payment terms are Net-30.",
    )
    app = build_ask_app(
        engagements=engagements,
        vector_index=vector_index,
        embedder=embedder,
        chat=FakeChatModel(error=ContextTooLargeError("Prompt exceeds the model context window.")),
    )
    response = await post_ask(app, engagement_id, {"question": "What are payment terms?"})
    assert response.status_code == 413
    body = response.json()
    assert body["code"] == "context_too_large"
    assert "context" in body["detail"].lower()
