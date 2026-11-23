"""Shared helpers for research agent graph nodes."""

from __future__ import annotations

from collections.abc import Sequence

from backend.application.agents.progress import AskProgress
from backend.application.agents.research_agent.prompts import AnswerGenerationResult
from backend.application.dto import ScoredChunk
from backend.application.llm.chat_model import ChatModel
from backend.domain.answer import (
    Citation,
    InsufficientEvidence,
    InsufficientReason,
    SuggestedClientQuestion,
)

from .suggestions import default_client_suggestions

_PARTIAL_CITATION_SNIPPET = 500
_PARTIAL_CITATION_LIMIT = 5


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def partial_citations_from_evidence(
    evidence: Sequence[ScoredChunk],
    *,
    limit: int = _PARTIAL_CITATION_LIMIT,
) -> tuple[Citation, ...]:
    """Build partial citations from the evidence bag for insufficient answers."""
    citations: list[Citation] = []
    for marker, row in enumerate(evidence[:limit], start=1):
        chunk = row.chunk
        snippet = chunk.text[:_PARTIAL_CITATION_SNIPPET].strip() or chunk.text[:_PARTIAL_CITATION_SNIPPET]
        if not snippet:
            continue
        citations.append(
            Citation(
                marker=marker,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_path=row.document_path,
                page=chunk.page,
                heading_path=chunk.heading_path,
                snippet=snippet,
                score=row.score,
            )
        )
    return tuple(citations)


def thinking_callbacks(chat: ChatModel, progress: AskProgress | None):
    if progress is None or not chat.supports_thinking:
        return None
    return progress.thinking_callbacks()


def insufficient_answer(
    question_text: str,
    *,
    reason: InsufficientReason,
    auditor_role: str | None,
    topic: str | None,
    partial_citations: tuple[Citation, ...] = (),
    uncertainties: tuple[str, ...] = (),
    suggested_client_questions: tuple[SuggestedClientQuestion, ...] | None = None,
) -> InsufficientEvidence:
    suggestions = (
        suggested_client_questions
        if suggested_client_questions is not None
        else default_client_suggestions(
            question_text,
            reason=reason,
            auditor_role=auditor_role,
            topic=topic,
        )
    )
    return InsufficientEvidence(
        reason=reason,
        partial_citations=partial_citations,
        uncertainties=uncertainties,
        suggested_client_questions=suggestions,
    )


def uncertainties_from_generation(generation: AnswerGenerationResult) -> tuple[str, ...]:
    items = tuple(
        _truncate(" ".join(item.split()), 500) for item in generation.uncertainties if item.strip()
    )
    if items:
        return items[:5]
    reason = generation.decline_reason.strip()
    if reason:
        return (_truncate(reason, 500),)
    return ()
