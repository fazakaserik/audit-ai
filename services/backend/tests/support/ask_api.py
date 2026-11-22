"""Helpers for offline ask API tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
from fastapi import FastAPI

from backend.api.dependencies import get_bound
from backend.api.main import create_app
from backend.application.ports import ChatModel, Embedder, VectorIndex
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


async def seed_engagement(
    engagements: InMemoryEngagementRepository,
    engagement_id: EngagementId,
    *,
    name: str = "Northwind FY2025",
) -> None:
    now = utc_now()
    await engagements.create(
        Engagement(id=engagement_id, name=name, created_at=now, updated_at=now)
    )


async def index_passage(
    vector_index: InMemoryVectorIndex,
    embedder: FakeEmbedder,
    *,
    engagement_id: EngagementId,
    path: str,
    text: str,
    page: int | None = 1,
) -> Passage:
    doc_id = DocumentId(uuid.uuid4())
    passage = Passage(
        id=PassageId(uuid.uuid4()),
        document_id=doc_id,
        document_version=1,
        ordinal=0,
        page=page,
        heading_path=(),
        text=text,
        token_count=max(1, len(text.split())),
        created_at=datetime.now(UTC),
    )
    embedded = await embedder.embed((text,))
    await vector_index.upsert_passages(
        engagement_id=engagement_id,
        document_id=doc_id,
        document_path=path,
        document_version=1,
        passages=(passage,),
        embeddings=(embedded.vectors[0],),
        embedding_model=embedder.model_name,
    )
    return passage


def answered_chat(text: str = "Payment is due within thirty days [1].") -> FakeChatModel:
    return FakeChatModel(
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text=text,
            markers_used=(1,),
        )
    )


def build_ask_app(
    *,
    engagements: InMemoryEngagementRepository,
    vector_index: VectorIndex | None = None,
    chat: ChatModel | None = None,
    embedder: Embedder | None = None,
) -> FastAPI:
    emb = embedder or FakeEmbedder()
    chat_model = chat or answered_chat()
    container = build_test_container(embedder=emb, chat=chat_model)
    bound = build_fakes_bound(
        engagements=engagements,
        vector_index=vector_index or InMemoryVectorIndex(),
    )
    app = create_app(settings=container.settings, container=container)

    async def override_bound():
        return bound

    app.dependency_overrides[get_bound] = override_bound
    return app


async def post_ask(
    app: FastAPI,
    engagement_id: EngagementId,
    payload: dict[str, object],
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.post(
            f"/api/v1/engagements/{engagement_id}/ask",
            json=payload,
        )
