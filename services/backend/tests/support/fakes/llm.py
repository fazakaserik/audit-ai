"""In-memory LLM fakes for offline tests."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TypeVar

from pydantic import BaseModel

from backend.application.dto import (
    ChatMessage,
    EmbedResult,
    IncompleteStructuredOutputError,
    StructuredResult,
    ThinkingCallbacks,
    ToolCall,
    ToolSpec,
    ToolTurnResult,
)
from backend.domain.errors import (
    ContextTooLargeError,
    ModelTimeoutError,
    ModelUnavailableError,
)
from backend.domain.session import LlmUsage

TModel = TypeVar("TModel", bound=BaseModel)

_DEFAULT_USAGE = LlmUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)


def agent_search_tool_turns(
    *,
    query: str = "search",
    answer: str | None = None,
    usage: LlmUsage | None = None,
) -> list[ToolTurnResult]:
    """Script one search tool round followed by a terminal answer turn."""
    call_usage = usage or _DEFAULT_USAGE
    return [
        ToolTurnResult(
            content=None,
            tool_calls=(
                ToolCall(
                    id="fake_search_1",
                    name="search_relevant_chunks",
                    arguments=json.dumps({"query": query}),
                ),
            ),
            usage=call_usage,
        ),
        ToolTurnResult(content=answer, tool_calls=(), usage=call_usage),
    ]


def repeat_agent_search_tool_turns(
    cycles: int,
    *,
    query: str = "search",
    usage: LlmUsage | None = None,
) -> list[ToolTurnResult]:
    turns: list[ToolTurnResult] = []
    call_usage = usage or _DEFAULT_USAGE
    for index in range(cycles):
        turns.append(
            ToolTurnResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        id=f"fake_search_{index + 1}",
                        name="search_relevant_chunks",
                        arguments=json.dumps({"query": query}),
                    ),
                ),
                usage=call_usage,
            )
        )
        turns.append(ToolTurnResult(content=None, tool_calls=(), usage=call_usage))
    return turns


class FakeChatModel:
    """Configurable ChatModel: return a pydantic instance or raise a model error.

    Pass ``tool_turns`` to script agent tool rounds; ``auto_search`` is opt-in legacy
    heuristic behavior (defaults to off).

    When a terminal tool turn has empty content, ``response.answer_text`` (if present)
    is used as the draft answer so older tests that only set ``response`` still work.
    When ``tools`` is empty (forced answer turn), scripted tool calls are skipped and
    the draft comes from the next content-only turn or ``response.answer_text``.
    """

    def __init__(
        self,
        *,
        response: BaseModel | None = None,
        responses: Sequence[BaseModel] | None = None,
        error: (
            ModelTimeoutError
            | ModelUnavailableError
            | ContextTooLargeError
            | IncompleteStructuredOutputError
            | None
        ) = None,
        supports_thinking: bool = False,
        thinking_text: str = "",
        thinking_seconds: float = 0.0,
        usage: LlmUsage | None = None,
        tool_turns: Sequence[ToolTurnResult] | None = None,
        auto_search: bool = False,
    ) -> None:
        self._response = response
        self._responses = list(responses) if responses is not None else None
        self._error = error
        self._supports_thinking = supports_thinking
        self._thinking_text = thinking_text
        self._thinking_seconds = thinking_seconds
        self._usage = usage or _DEFAULT_USAGE
        self._tool_turns = list(tool_turns) if tool_turns is not None else None
        self._auto_search = auto_search
        self.calls: list[tuple[tuple[ChatMessage, ...], type[BaseModel]]] = []
        self.tool_turn_calls: list[tuple[tuple[ChatMessage, ...], tuple[ToolSpec, ...]]] = []

    @property
    def supports_thinking(self) -> bool:
        return self._supports_thinking

    def configure(
        self,
        *,
        response: BaseModel | None = None,
        responses: Sequence[BaseModel] | None = None,
        error: (
            ModelTimeoutError
            | ModelUnavailableError
            | ContextTooLargeError
            | IncompleteStructuredOutputError
            | None
        ) = None,
        tool_turns: Sequence[ToolTurnResult] | None = None,
        auto_search: bool | None = None,
    ) -> None:
        self._response = response
        self._responses = list(responses) if responses is not None else None
        self._error = error
        if tool_turns is not None:
            self._tool_turns = list(tool_turns)
        if auto_search is not None:
            self._auto_search = auto_search

    def _draft_from_response(self) -> str | None:
        response = self._response
        if response is None and self._responses:
            response = self._responses[0]
        if response is None:
            return None
        text = getattr(response, "answer_text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
        return None

    def _answer_turn(self, *, usage: LlmUsage | None = None) -> ToolTurnResult:
        call_usage = usage or self._usage
        if self._tool_turns:
            while self._tool_turns and self._tool_turns[0].tool_calls:
                self._tool_turns.pop(0)
            if self._tool_turns:
                turn = self._tool_turns.pop(0)
                content = (turn.content or "").strip() or self._draft_from_response()
                return ToolTurnResult(content=content, tool_calls=(), usage=turn.usage)
        return ToolTurnResult(
            content=self._draft_from_response(),
            tool_calls=(),
            usage=call_usage,
        )

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> StructuredResult[TModel]:
        self.calls.append((tuple(messages), schema))
        if thinking is not None and self._supports_thinking:
            if self._thinking_text:
                await thinking.on_delta(self._thinking_text)
            thinking.on_seconds(self._thinking_seconds)
        if self._error is not None:
            raise self._error
        if self._responses:
            next_item = self._responses.pop(0)
            if not isinstance(next_item, schema):
                msg = (
                    f"FakeChatModel response type {type(next_item).__name__} "
                    f"does not match schema {schema.__name__}"
                )
                raise TypeError(msg)
            return StructuredResult(value=next_item, usage=self._usage)
        if self._response is None:
            msg = "FakeChatModel has no response configured"
            raise AssertionError(msg)
        if not isinstance(self._response, schema):
            msg = (
                f"FakeChatModel response type {type(self._response).__name__} "
                f"does not match schema {schema.__name__}"
            )
            raise TypeError(msg)
        return StructuredResult(value=self._response, usage=self._usage)

    async def complete_tool_turn(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> ToolTurnResult:
        self.tool_turn_calls.append((tuple(messages), tuple(tools)))
        if thinking is not None and self._supports_thinking:
            if self._thinking_text:
                await thinking.on_delta(self._thinking_text)
            thinking.on_seconds(self._thinking_seconds)
        if self._error is not None:
            raise self._error
        if not tools:
            return self._answer_turn()
        if self._tool_turns is not None:
            if not self._tool_turns:
                return ToolTurnResult(
                    content=self._draft_from_response(),
                    tool_calls=(),
                    usage=self._usage,
                )
            turn = self._tool_turns.pop(0)
            if turn.tool_calls:
                return turn
            content = (turn.content or "").strip() or self._draft_from_response()
            return ToolTurnResult(content=content, tool_calls=(), usage=turn.usage)
        has_tool_results = any(message.role == "tool" for message in messages)
        if self._auto_search and not has_tool_results:
            query = "search"
            for message in reversed(messages):
                if message.role == "user" and message.content:
                    query = message.content
                    break
            for line in reversed(query.splitlines()):
                stripped = line.strip()
                if stripped.lower().startswith("question:"):
                    query = stripped.split(":", 1)[1].strip() or query
                    break
            return ToolTurnResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        id=f"fake_search_{len(self.tool_turn_calls)}",
                        name="search_relevant_chunks",
                        arguments=json.dumps({"query": query}),
                    ),
                ),
                usage=self._usage,
            )
        return ToolTurnResult(
            content=self._draft_from_response(),
            tool_calls=(),
            usage=self._usage,
        )


class FakeEmbedder:
    def __init__(
        self,
        *,
        model_name: str = "fake-embed",
        dimensions: int = 8,
        usage: LlmUsage | None = None,
    ) -> None:
        self._model_name = model_name
        self._dimensions = dimensions
        self._usage = usage or LlmUsage(prompt_tokens=3, completion_tokens=0, total_tokens=3)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: Sequence[str]) -> EmbedResult:
        _ = texts
        base = [1.0] + [0.0] * (self._dimensions - 1)
        return EmbedResult(vectors=[list(base) for _ in texts], usage=self._usage)
