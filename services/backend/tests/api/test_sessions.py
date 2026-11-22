"""API tests: sessions created by ask, follow-up continues, cross-engagement 404."""

from __future__ import annotations

import httpx

from backend.rag.prompts import AnswerGenerationResult, CondenseQuestionResult
from domain.engagement import EngagementId
from support.ask_api import build_ask_app, index_passage, post_ask, seed_engagement
from support.fakes import (
    FakeChatModel,
    FakeEmbedder,
    InMemoryEngagementRepository,
    InMemoryVectorIndex,
)


async def test_ask_creates_session_and_follow_up_continues() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    engagements = InMemoryEngagementRepository()
    await seed_engagement(engagements, engagement_id)
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await index_passage(
        vector_index,
        embedder,
        engagement_id=engagement_id,
        path="contracts/contoso.pdf",
        text="Payment is due within thirty days of invoice.",
    )
    chat = FakeChatModel(
        responses=[
            AnswerGenerationResult(
                can_answer=True,
                answer_text="Thirty days [1].",
                markers_used=(1,),
            ),
            CondenseQuestionResult(
                standalone_question="What penalties apply for late Contoso payment?",
            ),
            AnswerGenerationResult(
                can_answer=True,
                answer_text="Penalties are not described in the excerpt [1].",
                markers_used=(1,),
            ),
        ],
    )
    app = build_ask_app(
        engagements=engagements,
        vector_index=vector_index,
        chat=chat,
        embedder=embedder,
    )

    first = await post_ask(app, engagement_id, {"question": "What are payment terms?"})
    assert first.status_code == 200
    first_body = first.json()
    session_id = first_body["session_id"]
    assert first_body["turn_id"]
    assert first_body["status"] == "answered"

    follow = await post_ask(
        app,
        engagement_id,
        {"question": "Any penalties?", "session_id": session_id},
    )
    assert follow.status_code == 200
    follow_body = follow.json()
    assert follow_body["session_id"] == session_id
    assert follow_body["turn_id"] != first_body["turn_id"]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        detail = await client.get(
            f"/api/v1/engagements/{engagement_id}/sessions/{session_id}",
        )
        assert detail.status_code == 200
        turns = detail.json()["turns"]
        assert len(turns) == 2
        assert turns[0]["standalone_question"] == "What are payment terms?"
        assert turns[1]["standalone_question"] == "What penalties apply for late Contoso payment?"


async def test_get_session_wrong_engagement_returns_404() -> None:
    engagement_a = EngagementId("northwind-fy2025")
    engagement_b = EngagementId("contoso-fy2025")
    engagements = InMemoryEngagementRepository()
    await seed_engagement(engagements, engagement_a, name="A")
    await seed_engagement(engagements, engagement_b, name="B")
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await index_passage(
        vector_index,
        embedder,
        engagement_id=engagement_a,
        path="a.pdf",
        text="Alpha evidence text for retrieval.",
    )
    app = build_ask_app(engagements=engagements, vector_index=vector_index, embedder=embedder)

    created = await post_ask(app, engagement_a, {"question": "Question on A?"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        wrong = await client.get(
            f"/api/v1/engagements/{engagement_b}/sessions/{session_id}",
        )
        assert wrong.status_code == 404
