"""LLM and embedding ports."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, TypeVar

from pydantic import BaseModel

from backend.application.dto import (
    ChatMessage,
    EmbedResult,
    StructuredResult,
    ThinkingCallbacks,
    ToolSpec,
    ToolTurnResult,
)

TModel = TypeVar("TModel", bound=BaseModel)


class ChatModel(Protocol):
    @property
    def supports_thinking(self) -> bool: ...

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> StructuredResult[TModel]: ...

    async def complete_tool_turn(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> ToolTurnResult: ...


class Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> EmbedResult: ...

    @property
    def model_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...
