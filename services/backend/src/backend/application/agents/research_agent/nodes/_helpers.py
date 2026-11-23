"""Shared helpers for research agent graph nodes."""

from __future__ import annotations

from backend.application.agents.progress import AskProgress
from backend.application.agents.research_agent.prompts import AnswerGenerationResult
from backend.application.llm.chat_model import ChatModel
from backend.domain.answer import (
    Citation,
    InsufficientEvidence,
    InsufficientReason,
    SuggestedClientQuestion,
)

from .suggestions import default_client_suggestions


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


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
