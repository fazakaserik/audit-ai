"""API test: cross-engagement isolation."""

from __future__ import annotations

from backend.domain.engagement import EngagementId
from support.ask_api import (
    answered_chat,
    build_ask_app,
    index_chunk,
    post_ask,
    seed_engagement,
)
from support.fakes import FakeEmbedder, InMemoryEngagementRepository, InMemoryVectorIndex


async def test_ask_does_not_see_other_engagement_chunks() -> None:
    target: EngagementId = "northwind-fy2025"
    other: EngagementId = "adventureworks-fy2024"
    engagements = InMemoryEngagementRepository()
    await seed_engagement(engagements, target)
    await seed_engagement(engagements, other, name="Adventure Works")

    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await index_chunk(
        vector_index,
        embedder,
        engagement_id=other,
        path="secret/other.md",
        text="Adventure Works secret payment terms are Net-7.",
    )

    app = build_ask_app(
        engagements=engagements,
        vector_index=vector_index,
        embedder=embedder,
        chat=answered_chat("Should not matter [1]."),
    )
    response = await post_ask(
        app,
        target,
        {"question": "What are the payment terms?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_evidence"
    assert body["reason"] == "no_relevant_chunks"
