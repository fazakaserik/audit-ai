"""Tool turns: accumulate streamed calls; retry without think if none."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from backend.application.dto import (
    ChatMessage,
    ThinkingCallbacks,
    ToolSpec,
)
from backend.infrastructure.litellm_chat import LiteLLMChatModel


def _tool_spec() -> ToolSpec:
    return ToolSpec(
        name="search_relevant_chunks",
        description="search",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
    )


async def _collect_deltas(text: str) -> None:
    _ = text


def _chat() -> LiteLLMChatModel:
    return LiteLLMChatModel(
        model="ollama_chat/test",
        api_key=None,
        api_base="http://test",
        timeout_seconds=30,
        max_concurrent_calls=1,
        supports_thinking=True,
    )


@pytest.mark.asyncio
async def test_tool_turn_retries_without_think_when_stream_emits_no_calls() -> None:
    chat = _chat()

    async def stream_no_tools() -> Any:
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content="I should call search_relevant_chunks.",
                        content=None,
                        tool_calls=None,
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content=None,
                        content=None,
                        tool_calls=None,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    cold = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id="call_1",
                            function=SimpleNamespace(
                                name="search_relevant_chunks",
                                arguments={"query": "services revenue 2025 Q1"},
                            ),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=6, total_tokens=17),
    )

    mock = AsyncMock(side_effect=[stream_no_tools(), cold])
    with patch.object(chat, "_acompletion", new=mock):
        seconds: list[float] = []
        result = await chat.complete_tool_turn(
            [ChatMessage(role="user", content="How much USD from services in 2025 Q1?")],
            [_tool_spec()],
            thinking=ThinkingCallbacks(on_delta=_collect_deltas, on_seconds=seconds.append),
        )

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "search_relevant_chunks"
    assert "services revenue" in result.tool_calls[0].arguments
    assert mock.await_count == 2
    assert seconds and seconds[0] > 0


@pytest.mark.asyncio
async def test_tool_turn_keeps_reading_after_thinking_budget() -> None:
    """Thinking budget stops deltas only; stream continues so late tool_calls arrive."""
    chat = _chat()

    async def stream_tools_after_budget() -> Any:
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content="x" * 100,
                        content=None,
                        tool_calls=None,
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content=None,
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="call_late",
                                function=SimpleNamespace(
                                    name="search_relevant_chunks",
                                    arguments={"query": "late"},
                                ),
                            )
                        ],
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content=None,
                        content=None,
                        tool_calls=None,
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=4, completion_tokens=3, total_tokens=7),
        )

    mock = AsyncMock(side_effect=[stream_tools_after_budget()])
    with (
        patch.object(chat, "_acompletion", new=mock),
        patch("backend.infrastructure.litellm_chat._THINKING_BUDGET_CHARS", 50),
    ):
        deltas: list[str] = []

        async def on_delta(text: str) -> None:
            deltas.append(text)

        result = await chat.complete_tool_turn(
            [ChatMessage(role="user", content="late tools?")],
            [_tool_spec()],
            thinking=ThinkingCallbacks(on_delta=on_delta, on_seconds=lambda _: None),
        )

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_late"
    assert mock.await_count == 1
    assert deltas and all(len(part) <= 100 for part in deltas)


@pytest.mark.asyncio
async def test_tool_turn_merges_fragmented_tool_call_deltas() -> None:
    chat = _chat()

    async def stream_fragmented() -> Any:
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content=None,
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id="call_frag",
                                function=SimpleNamespace(
                                    name="search_relevant_chunks", arguments=""
                                ),
                            )
                        ],
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content=None,
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id=None,
                                function=SimpleNamespace(
                                    name=None,
                                    arguments='{"query":"Q1 revenue"}',
                                ),
                            )
                        ],
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(reasoning_content=None, content=None, tool_calls=None),
                    finish_reason="tool_calls",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=2, completion_tokens=2, total_tokens=4),
        )

    mock = AsyncMock(side_effect=[stream_fragmented()])
    with patch.object(chat, "_acompletion", new=mock):
        result = await chat.complete_tool_turn(
            [ChatMessage(role="user", content="Q1?")],
            [_tool_spec()],
            thinking=ThinkingCallbacks(on_delta=_collect_deltas, on_seconds=lambda _: None),
        )

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_frag"
    assert result.tool_calls[0].name == "search_relevant_chunks"
    assert "Q1 revenue" in result.tool_calls[0].arguments
    assert mock.await_count == 1


@pytest.mark.asyncio
async def test_tool_turn_keeps_tool_calls_from_earlier_stream_chunk() -> None:
    chat = _chat()

    async def stream_with_mid_chunk_tools() -> Any:
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content="Searching…",
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="call_keep",
                                function=SimpleNamespace(
                                    name="search_relevant_chunks",
                                    arguments={"query": "Q1"},
                                ),
                            )
                        ],
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content=None,
                        content=None,
                        tool_calls=None,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5),
        )

    mock = AsyncMock(side_effect=[stream_with_mid_chunk_tools()])
    with patch.object(chat, "_acompletion", new=mock):
        result = await chat.complete_tool_turn(
            [ChatMessage(role="user", content="Q1 revenue?")],
            [_tool_spec()],
            thinking=ThinkingCallbacks(on_delta=_collect_deltas, on_seconds=lambda _: None),
        )

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_keep"
    assert mock.await_count == 1


@pytest.mark.asyncio
async def test_openai_tool_turn_uses_responses_model_id() -> None:
    chat = LiteLLMChatModel(
        model="openai/gpt-6-luna",
        api_key="sk-test",
        api_base=None,
        timeout_seconds=30,
        max_concurrent_calls=1,
    )
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id="call_1",
                            function=SimpleNamespace(
                                name="search_relevant_chunks",
                                arguments='{"query":"x"}',
                            ),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )
    mock = AsyncMock(return_value=response)
    with patch.object(chat, "_acompletion", new=mock):
        result = await chat.complete_tool_turn(
            [ChatMessage(role="user", content="q")],
            [_tool_spec()],
        )
    assert len(result.tool_calls) == 1
    assert mock.await_args is not None
    assert mock.await_args.kwargs["model"] == "openai/responses/gpt-6-luna"
