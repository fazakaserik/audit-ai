"""LangGraph state for the research agent workflow."""

from __future__ import annotations

from typing import TypedDict

from backend.application.dto import ChatMessage, ToolCall
from backend.domain.answer import Answer, Question
from backend.domain.session import LlmUsage


class State(TypedDict):
    question: Question
    standalone_question: str
    messages: list[ChatMessage]
    tool_rounds: int
    pending_tool_calls: tuple[ToolCall, ...]
    usage: LlmUsage
    draft_answer: str | None
    check_restarts: int
    answer: Answer | None
