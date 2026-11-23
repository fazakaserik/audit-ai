"""API test: no hits → insufficient_evidence + suggestions."""

from __future__ import annotations

from domain.engagement import EngagementId
from support.ask_api import build_ask_app, post_ask, seed_engagement
from support.fakes import InMemoryEngagementRepository


async def test_post_ask_insufficient_when_no_chunks() -> None:
    engagement_id: EngagementId = "northwind-fy2025"
    engagements = InMemoryEngagementRepository()
    await seed_engagement(engagements, engagement_id)
    app = build_ask_app(engagements=engagements)

    response = await post_ask(
        app,
        engagement_id,
        {"question": "What is the warranty period?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_evidence"
    assert body["reason"] == "no_relevant_chunks"
    assert 1 <= len(body["suggested_client_questions"]) <= 3
    assert "answer" not in body
    assert "session_id" in body
    assert "turn_id" in body
    assert "request_id" in body
