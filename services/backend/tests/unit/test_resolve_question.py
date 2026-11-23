"""Follow-up / retry standalone question resolution."""

from __future__ import annotations

import uuid

from backend.application.agents.research_agent.resolve_question import (
    resolve_standalone_question,
)
from backend.domain.answer import Answered, Question
from backend.domain.common import utc_now
from backend.domain.session import LlmUsage, SessionId, Turn, TurnId


def _turn(standalone: str) -> Turn:
    return Turn(
        id=TurnId(uuid.uuid4()),
        session_id=SessionId(uuid.uuid4()),
        ordinal=0,
        question=Question(text=standalone),
        standalone_question=standalone,
        answer=Answered(text="prior", citations=()),
        created_at=utc_now(),
        usage=LlmUsage(),
    )


def test_retry_phrase_reuses_prior_standalone() -> None:
    prior = (_turn("Who audited 4iG?"),)
    assert resolve_standalone_question("try again", prior) == "Who audited 4iG?"
    assert resolve_standalone_question("Try again!", prior) == "Who audited 4iG?"
    assert resolve_standalone_question("retry", prior) == "Who audited 4iG?"


def test_normal_question_unchanged() -> None:
    prior = (_turn("Who audited 4iG?"),)
    assert resolve_standalone_question("Who signed the report?", prior) == (
        "Who signed the report?"
    )


def test_retry_without_history_keeps_text() -> None:
    assert resolve_standalone_question("try again", ()) == "try again"
