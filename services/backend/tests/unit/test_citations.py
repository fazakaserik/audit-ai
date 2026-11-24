"""Unit tests for citation post-filtering."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from backend.application.agents.research_agent.citations import filter_and_build_citations
from backend.application.dto import ScoredChunk
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.document import DocumentId, DocumentPath


def _chunk(text: str) -> Chunk:
    now = datetime.now(UTC)
    return Chunk(
        id=ChunkId(uuid.uuid4()),
        document_id=DocumentId(uuid.uuid4()),
        document_version=1,
        ordinal=0,
        text=text,
        token_count=max(1, len(text.split())),
        created_at=now,
    )


def _scored(text: str, *, score: float = 0.9) -> ScoredChunk:
    return ScoredChunk(
        chunk=_chunk(text),
        document_path=DocumentPath("contracts/a.pdf"),
        score=score,
    )


def test_unknown_markers_dropped_and_renumbered() -> None:
    scored = (
        _scored("Payment is due in thirty days."),
        _scored("Renewal requires sixty days notice."),
    )
    result = filter_and_build_citations(
        "Terms are 30 days [1] and notice is 60 days [99] [2].",
        scored,
    )
    assert result is not None
    text, citations = result
    assert "[1]" in text and "[2]" in text
    assert "[99]" not in text
    assert len(citations) == 2
    assert citations[0].marker == 1
    assert citations[1].marker == 2
    assert citations[0].snippet.startswith("Payment")


def test_empty_when_no_evidence() -> None:
    assert filter_and_build_citations("No markers here.", ()) is None


def test_missing_markers_without_markers_used_rejected() -> None:
    scored = (_scored("Only chunk."),)
    assert filter_and_build_citations("Answer grounded in the only chunk.", scored) is None


def test_markers_used_salvages_missing_inline_markers() -> None:
    scored = (
        _scored("Payment is due in thirty days."),
        _scored("Quercus Audit Kft. signed the report."),
    )
    result = filter_and_build_citations(
        "Quercus Audit Kft. audited the company.",
        scored,
        markers_used=(2,),
    )
    assert result is not None
    text, citations = result
    assert text.endswith("[1]")
    assert len(citations) == 1
    assert citations[0].snippet.startswith("Quercus")
