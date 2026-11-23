"""API test: auditor_role/topic influence suggested client questions."""

from __future__ import annotations

from backend.domain.engagement import EngagementId
from support.ask_api import build_ask_app, post_ask, seed_engagement
from support.fakes import InMemoryEngagementRepository


async def test_suggestions_include_role_and_topic() -> None:
    engagement_id: EngagementId = "northwind-fy2025"
    engagements = InMemoryEngagementRepository()
    await seed_engagement(engagements, engagement_id)
    app = build_ask_app(engagements=engagements)

    response = await post_ask(
        app,
        engagement_id,
        {
            "question": "What is the SOC2 report conclusion?",
            "auditor_role": "ITGC",
            "topic": "access reviews",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_evidence"
    joined = " ".join(
        f"{item['question']} {item['rationale']}" for item in body["suggested_client_questions"]
    )
    assert "ITGC" in joined
    assert "access reviews" in joined
