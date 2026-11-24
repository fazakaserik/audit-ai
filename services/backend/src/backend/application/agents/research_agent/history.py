"""Bound recent session turns and summarize older ones for Ask prompts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from backend.application.agents.research_agent.prompts import format_prior_answer
from backend.application.dto import ChatMessage, IncompleteStructuredOutputError
from backend.application.llm.chat_model import ChatModel
from backend.domain.errors import DomainError
from backend.domain.session import LlmUsage, Turn
from backend.logging import get_logger

_CFG = ConfigDict(frozen=True, strict=True, extra="forbid")
_FALLBACK_SUMMARY_CHARS = 1_500
_ANSWER_STUB_CHARS = 120
log = get_logger(__name__)


class HistorySummaryResult(BaseModel):
    """Compact summary of older session turns (not evidence)."""

    model_config = _CFG

    summary: Annotated[str, Field(max_length=2_000)]


@dataclass(frozen=True, slots=True)
class SessionPromptContext:
    """History slice injected into agent/generate prompts."""

    recent_turns: tuple[Turn, ...]
    older_summary: str | None = None


def _fallback_summary(older: Sequence[Turn]) -> str:
    parts: list[str] = []
    for turn in older:
        answer = format_prior_answer(turn)
        if len(answer) > _ANSWER_STUB_CHARS:
            answer = f"{answer[: _ANSWER_STUB_CHARS - 3]}..."
        parts.append(f"- User: {turn.standalone_question}; Assistant: {answer}")
    text = "\n".join(parts)
    if len(text) <= _FALLBACK_SUMMARY_CHARS:
        return text
    return text[-_FALLBACK_SUMMARY_CHARS:]


def _summary_messages(older: Sequence[Turn]) -> tuple[ChatMessage, ...]:
    lines = [
        "Summarize the earlier part of an audit Q&A session in a few sentences.",
        "Keep entity names, amounts, dates, and open questions. Do not invent facts.",
        "This summary is only for resolving follow-up references; it is not evidence.",
        "",
        "Earlier turns:",
    ]
    for turn in older:
        lines.append(f"- User: {turn.standalone_question}")
        lines.append(f"  Assistant: {format_prior_answer(turn)}")
    return (
        ChatMessage(
            role="system",
            content="You compress chat history for an audit assistant. Output JSON only.",
        ),
        ChatMessage(role="user", content="\n".join(lines)),
    )


async def prepare_session_context(
    prior_turns: Sequence[Turn],
    *,
    max_recent: int,
    chat: ChatModel,
) -> tuple[SessionPromptContext, LlmUsage]:
    """Keep the last ``max_recent`` turns verbatim; summarize anything older."""
    turns = tuple(prior_turns)
    if not turns:
        return SessionPromptContext(recent_turns=()), LlmUsage()
    if len(turns) <= max_recent:
        return SessionPromptContext(recent_turns=turns), LlmUsage()

    older = turns[:-max_recent]
    recent = turns[-max_recent:]
    try:
        result = await chat.generate_structured(
            _summary_messages(older),
            HistorySummaryResult,
        )
        summary = result.value.summary.strip() or _fallback_summary(older)
        return (
            SessionPromptContext(recent_turns=recent, older_summary=summary),
            result.usage,
        )
    except (DomainError, IncompleteStructuredOutputError) as exc:
        log.warning(
            "session_history_summary_fallback",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return (
            SessionPromptContext(
                recent_turns=recent,
                older_summary=_fallback_summary(older),
            ),
            LlmUsage(),
        )
