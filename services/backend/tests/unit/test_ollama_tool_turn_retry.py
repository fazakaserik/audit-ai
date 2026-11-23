"""Ollama tool turns: accumulate streamed calls; retry without think if none."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.application.ports import ChatMessage, ThinkingCallbacks, ToolSpec
from backend.infrastructure.ollama_chat import OllamaChatModel


def _tool_spec() -> ToolSpec:
    return ToolSpec(
        name="search_relevant_chunks",
        description="search",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
    )


async def _collect_deltas(text: str) -> None:
    _ = text


@pytest.mark.asyncio
async def test_tool_turn_retries_without_think_when_stream_emits_no_calls() -> None:
    chat = OllamaChatModel(
        base_url="http://test",
        model="test",
        timeout_seconds=30,
        max_concurrent_calls=1,
        supports_thinking=True,
    )

    async def stream_no_tools() -> Any:
        yield SimpleNamespace(
            done=False,
            message=SimpleNamespace(
                thinking="I should call search_relevant_chunks.",
                content="",
                tool_calls=None,
            ),
        )
        yield SimpleNamespace(
            done=True,
            message=SimpleNamespace(thinking=None, content="", tool_calls=None),
            prompt_eval_count=10,
            eval_count=5,
        )

    cold = SimpleNamespace(
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
        prompt_eval_count=11,
        eval_count=6,
    )

    chat._client.chat = AsyncMock(side_effect=[stream_no_tools(), cold])

    seconds: list[float] = []
    result = await chat.complete_tool_turn(
        [ChatMessage(role="user", content="How much USD from services in 2025 Q1?")],
        [_tool_spec()],
        thinking=ThinkingCallbacks(on_delta=_collect_deltas, on_seconds=seconds.append),
    )

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "search_relevant_chunks"
    assert "services revenue" in result.tool_calls[0].arguments
    assert chat._client.chat.await_count == 2
    assert seconds and seconds[0] > 0


@pytest.mark.asyncio
async def test_tool_turn_keeps_tool_calls_from_earlier_stream_chunk() -> None:
    chat = OllamaChatModel(
        base_url="http://test",
        model="test",
        timeout_seconds=30,
        max_concurrent_calls=1,
        supports_thinking=True,
    )

    async def stream_with_mid_chunk_tools() -> Any:
        yield SimpleNamespace(
            done=False,
            message=SimpleNamespace(
                thinking="Searching…",
                content="",
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
        )
        # Final chunk often clears tool_calls; must not wipe earlier ones.
        yield SimpleNamespace(
            done=True,
            message=SimpleNamespace(thinking=None, content="", tool_calls=None),
            prompt_eval_count=3,
            eval_count=2,
        )

    chat._client.chat = AsyncMock(side_effect=[stream_with_mid_chunk_tools()])

    result = await chat.complete_tool_turn(
        [ChatMessage(role="user", content="Q1 revenue?")],
        [_tool_spec()],
        thinking=ThinkingCallbacks(on_delta=_collect_deltas, on_seconds=lambda _: None),
    )

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_keep"
    assert chat._client.chat.await_count == 1
