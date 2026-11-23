"""Shared helpers for the ask agent (suggestions)."""

from __future__ import annotations

from typing import assert_never

from domain.answer import InsufficientReason, SuggestedClientQuestion


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def default_client_suggestions(
    question_text: str,
    *,
    reason: InsufficientReason,
    auditor_role: str | None = None,
    topic: str | None = None,
) -> tuple[SuggestedClientQuestion, ...]:
    prompt = _truncate(question_text.strip(), 200)
    role_bit = f" for the {auditor_role} reviewer" if auditor_role else ""
    topic_bit = f" regarding {topic}" if topic else ""
    match reason:
        case InsufficientReason.NO_RELEVANT_CHUNKS:
            return (
                SuggestedClientQuestion(
                    question=(
                        f"Can you provide documents{role_bit} that answer: {prompt}{topic_bit}?"
                    ),
                    rationale="No indexed chunks met the relevance threshold for this question.",
                ),
                SuggestedClientQuestion(
                    question=(
                        "Are there additional files in a different folder that cover "
                        f"this{topic_bit or ' topic'}?"
                    ),
                    rationale="The current folder scope may not include the relevant records.",
                ),
            )
        case InsufficientReason.MODEL_JUDGED_INSUFFICIENT:
            return (
                SuggestedClientQuestion(
                    question=(
                        "Can you restate the question with a concrete audit topic"
                        f"{topic_bit}{role_bit}?"
                    ),
                    rationale=(
                        "The assistant declined because the question was unclear "
                        "or the retrieved evidence was not enough to ground an answer."
                    ),
                ),
                SuggestedClientQuestion(
                    question=(
                        f"Can you provide clearer or additional documentation{role_bit} "
                        f"about: {prompt}{topic_bit}?"
                    ),
                    rationale="Additional source material may make a grounded answer possible.",
                ),
            )
    assert_never(reason)
