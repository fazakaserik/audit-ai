"""Unit tests for insufficient-evidence client question suggestions."""

from __future__ import annotations

from backend.application.rag.nodes import default_client_suggestions
from backend.domain.answer import InsufficientReason


def test_suggestions_are_the_audit_ask_not_meta_prompts() -> None:
    suggestions = default_client_suggestions(
        "the documents prove handling of prepayments?",
        reason=InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
    )
    assert len(suggestions) == 1
    assert suggestions[0].question == "the documents prove handling of prepayments?"
    assert "restate" not in suggestions[0].question.lower()
    assert "documentation about:" not in suggestions[0].question.lower()


def test_suggestions_include_role_and_topic_in_rationale() -> None:
    suggestions = default_client_suggestions(
        "SOC2 report conclusion?",
        reason=InsufficientReason.NO_RELEVANT_CHUNKS,
        auditor_role="ITGC",
        topic="access reviews",
    )
    joined = " ".join(f"{item.question} {item.rationale}" for item in suggestions)
    assert "ITGC" in joined
    assert "access reviews" in joined
    assert suggestions[0].question == "SOC2 report conclusion?"
