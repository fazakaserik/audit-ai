"""Node runtime context shared across graph steps."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from backend.application.agents.progress import AskProgress
from backend.application.llm.chat_model import ChatModel
from backend.application.tools.base import ToolContext
from backend.config import Settings
from backend.domain.session import Turn

TOOL_NAMES: tuple[str, ...] = (
    "search_relevant_chunks",
    "list_documents",
    "read_document",
    "get_current_time",
)


@dataclass(frozen=True, slots=True)
class NodeContext:
    chat: ChatModel
    settings: Settings
    tool_ctx: ToolContext
    progress: AskProgress | None
    prior_turns: Sequence[Turn] = ()
