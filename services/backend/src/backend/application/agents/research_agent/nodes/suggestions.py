"""Client question suggestions for insufficient-evidence answers."""

from __future__ import annotations

from typing import assert_never

from backend.application.agents.research_agent.prompts import AnswerGenerationResult
from backend.domain.answer import InsufficientReason, SuggestedClientQuestion


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def topic_phrase(question_text: str) -> str:
    cleaned = " ".join(question_text.split()).strip().rstrip("?.!")
    if not cleaned:
        return "this topic"
    return _truncate(cleaned, 200)


def _as_full_question(text: str) -> str:
    """Normalize to a single full interrogative ending with '?'."""
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return ""
    cleaned = cleaned.rstrip("?.!") + "?"
    return _truncate(cleaned, 500)


def default_client_suggestions(
    question_text: str,
    *,
    reason: InsufficientReason,
    auditor_role: str | None = None,
    topic: str | None = None,
) -> tuple[SuggestedClientQuestion, ...]:
    """Fallback full questions for missing material — never echo a yes/no restatement."""
    phrase = topic_phrase(question_text)
    role_note = f" Scoped for the {auditor_role} reviewer." if auditor_role else ""
    topic_note = f" Topic focus: {topic}." if topic else ""
    match reason:
        case InsufficientReason.NO_RELEVANT_CHUNKS:
            return (
                SuggestedClientQuestion(
                    question=_as_full_question(f"Which documents define or cover {phrase}"),
                    rationale=(
                        "No indexed chunks met the relevance threshold for this question."
                        f"{role_note}{topic_note}"
                    ),
                ),
            )
        case InsufficientReason.MODEL_JUDGED_INSUFFICIENT:
            return (
                SuggestedClientQuestion(
                    question=_as_full_question(f"What definition or policy clause covers {phrase}"),
                    rationale=(
                        "Retrieved evidence was not enough to ground a confident answer."
                        f"{role_note}{topic_note}"
                    ),
                ),
            )
    assert_never(reason)


def suggestions_from_generation(
    generation: AnswerGenerationResult,
    *,
    question_text: str,
    auditor_role: str | None,
    topic: str | None,
) -> tuple[SuggestedClientQuestion, ...]:
    """Prefer model client questions; fall back to deterministic defaults."""
    cleaned: list[SuggestedClientQuestion] = []
    uncertainties = tuple(
        _truncate(" ".join(item.split()), 500) for item in generation.uncertainties if item.strip()
    )
    rationale_base = (
        uncertainties[0]
        if uncertainties
        else (generation.decline_reason.strip() or "Evidence does not fully support an answer.")
    )
    for raw in generation.client_questions:
        ask = _as_full_question(raw)
        if len(ask) < 2:
            continue
        cleaned.append(SuggestedClientQuestion(question=ask, rationale=rationale_base))
        if len(cleaned) >= 3:
            break
    if cleaned:
        return tuple(cleaned)
    return default_client_suggestions(
        question_text,
        reason=InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
        auditor_role=auditor_role,
        topic=topic,
    )
