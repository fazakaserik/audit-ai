"""Resolve follow-up / retry prompts to a standalone question for this turn."""

from __future__ import annotations

import re
from collections.abc import Sequence

from backend.domain.session import Turn

_RETRY_RE = re.compile(
    r"^(try\s*again|again|retry|please\s+(try\s+again|retry)|once\s+more|"
    r"re-?ask|one\s+more\s+time)\.?!?$",
    re.IGNORECASE,
)


def resolve_standalone_question(
    question_text: str,
    prior_turns: Sequence[Turn],
) -> str:
    """Map retry phrases to the prior standalone question; otherwise keep the text."""
    cleaned = " ".join(question_text.split()).strip()
    if not cleaned:
        return question_text.strip() or question_text
    if prior_turns and _RETRY_RE.match(cleaned):
        prior = prior_turns[-1].standalone_question.strip()
        if prior:
            return prior
    return cleaned
