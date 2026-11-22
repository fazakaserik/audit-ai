"""API test: POST ask returns answered shape with citations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx

from backend.api.dependencies import get_bound
from backend.api.main import create_app
from backend.rag.prompts import AnswerGenerationResult
from domain.common import utc_now
from domain.document import DocumentId
from domain.engagement import Engagement, EngagementId
from domain.passage import Passage, PassageId
from support.fakes import (
    FakeChatModel,
    FakeEmbedder,
    InMemoryEngagementRepository,
    InMemoryVectorIndex,
)
from support.test_container import build_fakes_bound, build_test_container


async def test_post_ask_answered_with_citations() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    engagements = InMemoryEngagementRepository()
    now = utc_now()
    await engagements.create(
        Engagement(
            id=engagement_id,
            name="Northwind FY2025",
            created_at=now,
            updated_at=now,
        )
    )

    passage_text = "The Contoso agreement requires payment within thirty days of invoice date."
    doc_id = DocumentId(uuid.uuid4())
    passage = Passage(
        id=PassageId(uuid.uuid4()),
        document_id=doc_id,
        document_version=1,
        ordinal=0,
        page=3,
        heading_path=("Payment terms",),
        text=passage_text,
        token_count=12,
        created_at=datetime.now(UTC),
    )

    embedder = FakeEmbedder()
    embedded = await embedder.embed((passage_text, "payment terms contoso"))
    vector_index = InMemoryVectorIndex()
    await vector_index.upsert_passages(
        engagement_id=engagement_id,
        document_id=doc_id,
        document_path="contracts/contoso.pdf",
        document_version=1,
        passages=(passage,),
        embeddings=(embedded.vectors[0],),
        embedding_model=embedder.model_name,
    )

    chat = FakeChatModel(
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Payment is due within thirty days [1].",
            markers_used=(1,),
        ),
    )
    container = build_test_container(embedder=embedder, chat=chat)
    settings = container.settings
    bound = build_fakes_bound(engagements=engagements, vector_index=vector_index)
    app = create_app(settings=settings, container=container)

    async def override_bound():
        return bound

    app.dependency_overrides[get_bound] = override_bound

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/v1/engagements/{engagement_id}/ask",
            json={"question": "What are the Contoso payment terms?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert "[1]" in body["answer"]
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["document_path"] == "contracts/contoso.pdf"
    assert body["citations"][0]["marker"] == 1
    assert "session_id" in body
    assert "turn_id" in body
    assert "request_id" in body
    assert body["usage"]["prompt_tokens"] >= 10
    assert body["usage"]["completion_tokens"] >= 5
    assert body["usage"]["total_tokens"] >= 15
    assert body["session_total_tokens"] == body["usage"]["total_tokens"]
