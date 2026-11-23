"""Provider-agnostic ask progress events for streaming UIs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from backend.application.dto import ThinkingCallbacks
from backend.domain.document import DocumentPath

AskStage = Literal[
    "agent",
    "tool",
    "generate",
    "suggest",
    "finalize",
    # Legacy stages kept for older clients / transitional tests
    "condense",
    "retrieve",
    "grade",
]


@dataclass(frozen=True, slots=True)
class SourceHit:
    path: DocumentPath
    score: float


class AskProgress(Protocol):
    async def stage(self, name: AskStage) -> None: ...

    async def sources(self, items: Sequence[SourceHit]) -> None: ...

    async def tool_call(self, *, name: str, arguments: str) -> None: ...

    async def tool_result(self, *, name: str, summary: str) -> None: ...

    async def thinking_delta(self, text: str) -> None: ...

    def add_thinking_seconds(self, seconds: float) -> None: ...

    def thinking_callbacks(self) -> ThinkingCallbacks: ...


@dataclass
class CollectingAskProgress:
    """In-memory progress sink used by SSE and tests."""

    stages: list[AskStage] = field(default_factory=list)
    source_batches: list[tuple[SourceHit, ...]] = field(default_factory=list)
    tool_calls: list[tuple[str, str]] = field(default_factory=list)
    tool_results: list[tuple[str, str]] = field(default_factory=list)
    thinking_chunks: list[str] = field(default_factory=list)
    thinking_seconds: float = 0.0
    _emit: Callable[[dict[str, object]], Awaitable[None]] | None = None

    def bind_emitter(self, emit: Callable[[dict[str, object]], Awaitable[None]]) -> None:
        self._emit = emit

    async def stage(self, name: AskStage) -> None:
        self.stages.append(name)
        if self._emit is not None:
            await self._emit({"type": "stage", "stage": name})

    async def sources(self, items: Sequence[SourceHit]) -> None:
        batch = tuple(items)
        self.source_batches.append(batch)
        if self._emit is not None:
            await self._emit(
                {
                    "type": "sources",
                    "sources": [{"path": hit.path, "score": hit.score} for hit in batch],
                }
            )

    async def tool_call(self, *, name: str, arguments: str) -> None:
        self.tool_calls.append((name, arguments))
        if self._emit is not None:
            await self._emit({"type": "tool_call", "name": name, "arguments": arguments})

    async def tool_result(self, *, name: str, summary: str) -> None:
        self.tool_results.append((name, summary))
        if self._emit is not None:
            await self._emit({"type": "tool_result", "name": name, "summary": summary})

    async def thinking_delta(self, text: str) -> None:
        if not text:
            return
        self.thinking_chunks.append(text)
        if self._emit is not None:
            await self._emit({"type": "thinking_delta", "text": text})

    def add_thinking_seconds(self, seconds: float) -> None:
        if seconds > 0:
            self.thinking_seconds += seconds

    def thinking_callbacks(self) -> ThinkingCallbacks:
        return ThinkingCallbacks(
            on_delta=self.thinking_delta,
            on_seconds=self.add_thinking_seconds,
        )
