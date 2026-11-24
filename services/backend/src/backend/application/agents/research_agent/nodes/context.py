"""Node runtime context shared across graph steps."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.application.agents.progress import AskProgress
from backend.application.agents.research_agent.history import SessionPromptContext
from backend.application.llm.chat_model import ChatModel
from backend.application.tools.base import ToolContext
from backend.config import Settings

TOOL_NAMES: tuple[str, ...] = (
    "search_relevant_chunks",
    "list_documents",
    "read_document",
    "get_current_time",
)


def _empty_session_context() -> SessionPromptContext:
    return SessionPromptContext(recent_turns=())


@dataclass(frozen=True, slots=True)
class NodeContext:
    chat: ChatModel
    settings: Settings
    tool_ctx: ToolContext
    progress: AskProgress | None
    session_context: SessionPromptContext = field(default_factory=_empty_session_context)
