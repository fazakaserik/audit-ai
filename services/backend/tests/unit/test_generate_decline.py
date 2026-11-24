"""Ungrounded or empty drafts become insufficient after the evidence check."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from backend.application.agents.research_agent.graph import GraphDeps, run_graph
from backend.application.dto import ToolCall, ToolTurnResult
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
) -> GraphDeps:
    return GraphDeps(
        chat=chat,
        embedder=embedder,
        vector_index=vector_index,
        engagements=InMemoryEngagementRepository(),
        documents=InMemoryDocumentRepository(),
        storage=InMemoryDocumentStorage(),
        settings=Settings(relevance_threshold=0.0, agent_max_check_restarts=0),
    )


def _search_then_blank() -> list[ToolTurnResult]:
    return [
        ToolTurnResult(
            content=None,
            tool_calls=(
                ToolCall(
                    id="fake_search_1",
                    name="search_relevant_chunks",
                    arguments=json.dumps({"query": "search"}),
                ),
            ),
            usage=LlmUsage(),
        ),
        ToolTurnResult(content=None, tool_calls=(), usage=LlmUsage()),
    ]


async def test_empty_draft_after_retrieval_is_insufficient() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await _seed_hit(vector_index, embedder, engagement_id)
    chat = FakeChatModel(tool_turns=_search_then_blank(), usage=LlmUsage())
    result = await run_graph(
        engagement_id=engagement_id,
        question=Question(text=".."),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(chat, vector_index, embedder),
    )
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.reason == InsufficientReason.MODEL_JUDGED_INSUFFICIENT
    assert result.answer.partial_citations
    assert result.answer.partial_citations[0].snippet.startswith("Some policy")


async def test_blank_answer_turn_becomes_insufficient_not_crash() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await _seed_hit(vector_index, embedder, engagement_id)
    chat = FakeChatModel(tool_turns=_search_then_blank(), usage=LlmUsage())
    result = await run_graph(
        engagement_id=engagement_id,
        question=Question(text=".."),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(chat, vector_index, embedder),
    )
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.reason == InsufficientReason.MODEL_JUDGED_INSUFFICIENT
