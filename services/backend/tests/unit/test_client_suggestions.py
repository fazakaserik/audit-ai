"""Unit tests for insufficient-evidence client question suggestions."""

from __future__ import annotations

from backend.application.agents.research_agent.nodes import (
    default_client_suggestions,
    suggestions_from_generation,
    uncertainties_from_generation,
)
from backend.application.agents.research_agent.prompts import AnswerGenerationResult
from backend.domain.answer import InsufficientReason


def test_suggestions_are_full_questions_not_echo_yes_no() -> None:
    suggestions = default_client_suggestions(
        "so beer cannot be paid?",
        reason=InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
    )
    assert len(suggestions) == 1
    question = suggestions[0].question
    assert question.endswith("?")
    assert question[0].isupper()
    assert "beer" in question.lower()
    assert question != "so beer cannot be paid?"
    assert question.lower().startswith(("what ", "which ", "who ", "how "))


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
    assert suggestions[0].question.startswith("Which documents")


def test_model_client_questions_preferred_over_defaults() -> None:
    generation = AnswerGenerationResult(
        can_answer=False,
        decline_reason="Policy discusses alcohol, not beer by name.",
        uncertainties=("Whether beer is treated as alcohol under this policy",),
        client_questions=("What is the definition of beer under this policy?",),
    )
    suggestions = suggestions_from_generation(
        generation,
        question_text="so beer cannot be paid?",
        auditor_role=None,
        topic=None,
    )
    assert suggestions[0].question == "What is the definition of beer under this policy?"
    assert (
        "alcohol" in suggestions[0].rationale.lower() or "beer" in suggestions[0].rationale.lower()
    )
    assert uncertainties_from_generation(generation) == (
        "Whether beer is treated as alcohol under this policy",
    )
