"""CLI parses ask usage from the API and feeds the sticky footer."""

from __future__ import annotations

import uuid

import httpx
import pytest

from backend.api.contracts.v1.responses import AskResponseRoot
from backend.api.dependencies import get_bound
from backend.api.main import create_app
from backend.rag.prompts import AnswerGenerationResult
from cli.repl import ReplState, _token_toolbar
from domain.common import utc_now
from domain.document import DocumentId
from domain.engagement import Engagement, EngagementId
from domain.chunk import Chunk, ChunkId
from support.fakes import (
    FakeChatModel,
    FakeEmbedder,
    InMemoryEngagementRepository,
    InMemoryVectorIndex,
)
from support.test_container import build_fakes_bound, build_test_container


@pytest.mark.asyncio
async def test_cli_toolbar_updates_from_ask_response() -> None:
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

    chunk_text = "Payment is due within thirty days."
    doc_id = DocumentId(uuid.uuid4())
    chunk = Chunk(
        id=ChunkId(uuid.uuid4()),
        document_id=doc_id,
        document_version=1,
        ordinal=0,
        page=1,
        heading_path=(),
        text=chunk_text,
        token_count=8,
        created_at=now,
    )
    embedder = FakeEmbedder()
    embedded = await embedder.embed((chunk_text,))
    vector_index = InMemoryVectorIndex()
    await vector_index.upsert_chunks(
        engagement_id=engagement_id,
        document_id=doc_id,
        document_path="contracts/contoso.pdf",
        document_version=1,
        chunks=(chunk,),
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
    bound = build_fakes_bound(engagements=engagements, vector_index=vector_index)
    app = create_app(settings=container.settings, container=container)

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
    ask = AskResponseRoot.model_validate_json(response.content).root
    state = ReplState()
    state.apply_usage_from_answer(ask)
    toolbar = str(_token_toolbar(state))
    assert str(ask.usage.prompt_tokens) in toolbar
    assert str(ask.usage.total_tokens) in toolbar
    assert str(ask.session_total_tokens) in toolbar
    assert "—" not in toolbar
