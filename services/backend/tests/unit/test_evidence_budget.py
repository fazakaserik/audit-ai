"""Evidence bag ceiling is enforced when tools append chunks."""

from __future__ import annotations

import uuid

from backend.application.dto import ScoredChunk
from backend.application.tools.base import ToolContext, append_evidence_within_budget
from backend.application.tools.search_relevant_chunks import (
    SearchRelevantChunksArgs,
    SearchRelevantChunksTool,
)
from backend.config import Settings
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.common import utc_now
from backend.domain.document import DocumentId
from backend.domain.engagement import EngagementId
from support.fakes import (
    FakeEmbedder,
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
    InMemoryEngagementRepository,
    InMemoryVectorIndex,
)


def _chunk(text: str) -> ScoredChunk:
    return ScoredChunk(
        chunk=Chunk(
            id=ChunkId(uuid.uuid4()),
            document_id=DocumentId(uuid.uuid4()),
            document_version=1,
            ordinal=0,
            page=1,
            heading_path=(),
            text=text,
            token_count=max(1, len(text.split())),
            created_at=utc_now(),
        ),
        document_path="docs/a.md",
        score=0.9,
    )


def _ctx(*, evidence_max: int, relevance_threshold: float = 0.3) -> ToolContext:
    return ToolContext(
        engagement_id=EngagementId("northwind-fy2025"),
        folder_scope=None,
        embedder=FakeEmbedder(),
        vector_index=InMemoryVectorIndex(),
        engagements=InMemoryEngagementRepository(),
        documents=InMemoryDocumentRepository(),
        storage=InMemoryDocumentStorage(),
        settings=Settings(
            agent_evidence_max_chars=evidence_max,
            agent_read_max_chars=50_000,
            relevance_threshold=relevance_threshold,
        ),
    )


def test_append_evidence_stops_at_bag_ceiling() -> None:
    ctx = _ctx(evidence_max=2_000)
    first = _chunk("a" * 1_200)
    second = _chunk("b" * 1_200)
    third = _chunk("c" * 1_200)
    added, truncated = append_evidence_within_budget(ctx, (first, second, third))
    assert [row.chunk.id for row in added] == [first.chunk.id]
    assert truncated is True
    assert len(ctx.evidence) == 1


def test_append_evidence_respects_per_call_cap() -> None:
    ctx = _ctx(evidence_max=10_000)
    rows = (_chunk("x" * 400), _chunk("y" * 400), _chunk("z" * 400))
    added, truncated = append_evidence_within_budget(ctx, rows, per_call_max_chars=500)
    assert len(added) == 1
    assert truncated is True


async def test_search_with_full_bag_does_not_crash() -> None:
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    ctx = ToolContext(
        engagement_id=EngagementId("northwind-fy2025"),
        folder_scope=None,
        embedder=embedder,
        vector_index=vector_index,
        engagements=InMemoryEngagementRepository(),
        documents=InMemoryDocumentRepository(),
        storage=InMemoryDocumentStorage(),
        settings=Settings(
            agent_evidence_max_chars=2_000,
            agent_read_max_chars=50_000,
            relevance_threshold=0.0,
        ),
        evidence=[_chunk("f" * 2_000)],
    )
    hit = _chunk("hit text that cannot fit")
    embedded = await embedder.embed((hit.chunk.text,))
    await vector_index.upsert_chunks(
        engagement_id=ctx.engagement_id,
        document_id=hit.chunk.document_id,
        document_path=hit.document_path,
        document_version=1,
        chunks=(hit.chunk,),
        embeddings=(embedded.vectors[0],),
        embedding_model=embedder.model_name,
    )
    result = await SearchRelevantChunksTool().run(
        ctx,
        SearchRelevantChunksArgs(query="hit", folder_prefix=None),
    )
    assert "added 0 to evidence" in result.content
    assert "AGENT_EVIDENCE_MAX_CHARS" in result.content
