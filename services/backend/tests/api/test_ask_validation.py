"""API test: empty/invalid question → 422 Problem Details."""

from __future__ import annotations

from domain.engagement import EngagementId
from support.ask_api import build_ask_app, post_ask, seed_engagement
from support.fakes import InMemoryEngagementRepository


async def test_empty_question_returns_validation_error() -> None:
    engagement_id: EngagementId = "northwind-fy2025"
    engagements = InMemoryEngagementRepository()
    await seed_engagement(engagements, engagement_id)
    app = build_ask_app(engagements=engagements)

    response = await post_ask(app, engagement_id, {"question": "   "})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["status"] == 422
    assert "request_id" in body
