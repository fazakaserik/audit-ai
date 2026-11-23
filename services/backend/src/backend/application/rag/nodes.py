"""Shared helpers for the ask agent (suggestions)."""

from __future__ import annotations

from typing import assert_never

from backend.domain.answer import InsufficientReason, SuggestedClientQuestion


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _client_ask(question_text: str) -> str:
    """Topic line that completes 'May I ask you to give me more:' in the CLI."""
    cleaned = " ".join(question_text.split()).strip().rstrip("?.!")
    if not cleaned:
        cleaned = "this topic"
    return _truncate(f"{cleaned}?", 500)


def default_client_suggestions(
    question_text: str,
    *,
    reason: InsufficientReason,
    auditor_role: str | None = None,
    topic: str | None = None,
) -> tuple[SuggestedClientQuestion, ...]:
    ask = _client_ask(question_text)
    role_note = f" Scoped for the {auditor_role} reviewer." if auditor_role else ""
    topic_note = f" Topic focus: {topic}." if topic else ""
    match reason:
        case InsufficientReason.NO_RELEVANT_CHUNKS:
            return (
                SuggestedClientQuestion(
                    question=ask,
                    rationale=(
                        "No indexed chunks met the relevance threshold for this question."
                        f"{role_note}{topic_note}"
                    ),
                ),
            )
        case InsufficientReason.MODEL_JUDGED_INSUFFICIENT:
            return (
                SuggestedClientQuestion(
                    question=ask,
                    rationale=(
                        "Retrieved evidence was not enough to ground a confident answer."
                        f"{role_note}{topic_note}"
                    ),
                ),
            )
    assert_never(reason)
