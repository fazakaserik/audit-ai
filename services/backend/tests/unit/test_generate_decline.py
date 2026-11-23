"""Agent declines cleanly when the model cannot answer after retrieval."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TypeVar

from pydantic import BaseModel

from backend.application.ports import (
    ChatMessage,
    IncompleteStructuredOutputError,
    StructuredResult,
    ThinkingCallbacks,
)
from backend.application.rag.agent import AskAgentDeps, run_ask_agent
from backend.application.rag.prompts import AnswerGenerationResult
from backend.config import Settings
from backend.domain.answer import AnswerStatus, InsufficientReason, Question
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.document import DocumentId
from backend.domain.engagement import EngagementId
from backend.domain.session import LlmUsage
from support.fakes import (
    FakeChatModel,
    FakeEmbedder,
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
    InMemoryEngagementRepository,
    InMemoryVectorIndex,
)

TModel = TypeVar("TModel", bound=BaseModel)


async def _seed_hit(
    vector_index: InMemoryVectorIndex,
    embedder: FakeEmbedder,
    engagement_id: EngagementId,
) -> None:
    chunk = Chunk(
        id=ChunkId(uuid.uuid4()),
        document_id=DocumentId(uuid.uuid4()),
        document_version=1,
        ordinal=0,
        page=1,
        heading_path=(),
        text="Some policy text.",
        token_count=4,
        created_at=datetime.now(UTC),
    )
    embedded = await embedder.embed((chunk.text,))
    await vector_index.upsert_chunks(
        engagement_id=engagement_id,
        document_id=chunk.document_id,
        document_path="policies/a.md",
        document_version=1,
        chunks=(chunk,),
        embeddings=(embedded.vectors[0],),
        embedding_model=embedder.model_name,
    )


def _deps(
    chat: FakeChatModel, vector_index: InMemoryVectorIndex, embedder: FakeEmbedder
) -> AskAgentDeps:
    return AskAgentDeps(
        chat=chat,
        embedder=embedder,
        vector_index=vector_index,
        engagements=InMemoryEngagementRepository(),
        documents=InMemoryDocumentRepository(),
        storage=InMemoryDocumentStorage(),
        settings=Settings(relevance_threshold=0.0),
    )


class _StructuredFailChat(FakeChatModel):
    """Runs the normal tool loop, then fails structured generation."""

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> StructuredResult[TModel]:
        _ = (messages, schema, thinking)
        raise IncompleteStructuredOutputError("empty content")


async def test_model_decline_routes_to_insufficient() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await _seed_hit(vector_index, embedder, engagement_id)
    chat = FakeChatModel(
        response=AnswerGenerationResult(
            can_answer=False,
            answer_text="",
            decline_reason="The question is not understandable.",
            markers_used=(),
        ),
    )
    result = await run_ask_agent(
        engagement_id=engagement_id,
        question=Question(text=".."),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(chat, vector_index, embedder),
    )
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.reason == InsufficientReason.MODEL_JUDGED_INSUFFICIENT


async def test_incomplete_structured_output_becomes_decline_not_crash() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await _seed_hit(vector_index, embedder, engagement_id)
    chat = _StructuredFailChat(
        response=AnswerGenerationResult(can_answer=True, answer_text="x [1]", markers_used=(1,)),
        usage=LlmUsage(),
    )
    result = await run_ask_agent(
        engagement_id=engagement_id,
        question=Question(text=".."),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(chat, vector_index, embedder),
    )
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.reason == InsufficientReason.MODEL_JUDGED_INSUFFICIENT
