"""Structured generate: keep reading after thinking budget; cold-retry if no JSON."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, ConfigDict

import backend.infrastructure.litellm_chat as chat_mod
from backend.application.dto import ChatMessage, ThinkingCallbacks
from backend.infrastructure.litellm_chat import LiteLLMChatModel


class _TinyResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    can_answer: bool
    answer_text: str = ""


async def _collect_deltas(text: str) -> None:
    _ = text


def _chat(
    *,
    supports_thinking: bool = True,
) -> LiteLLMChatModel:
    return LiteLLMChatModel(
        model="ollama_chat/test",
        api_key=None,
        api_base="http://test",
        timeout_seconds=30,
        max_concurrent_calls=1,
        supports_thinking=supports_thinking,
    )


@pytest.mark.asyncio
async def test_structured_does_not_abort_stream_before_json_content() -> None:
    chat = _chat()

    async def stream_think_then_json() -> Any:
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(reasoning_content="x" * 100, content=None),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content="",
                        content='{"can_answer": true, "answer_text": "yes"}',
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(reasoning_content=None, content=None),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    mock = AsyncMock(side_effect=[stream_think_then_json()])
    with patch.object(chat, "_acompletion", new=mock):
        original_chars = chat_mod._THINKING_BUDGET_CHARS
        chat_mod._THINKING_BUDGET_CHARS = 10
        try:
            result = await chat.generate_structured(
                (ChatMessage(role="user", content="q"),),
                _TinyResult,
                thinking=ThinkingCallbacks(on_delta=_collect_deltas, on_seconds=lambda _: None),
            )
        finally:
            chat_mod._THINKING_BUDGET_CHARS = original_chars

    assert result.value.can_answer is True
    assert result.value.answer_text == "yes"
    assert mock.await_count == 1


@pytest.mark.asyncio
async def test_structured_retries_without_think_when_stream_has_no_json() -> None:
    chat = _chat()

    async def stream_think_only() -> Any:
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content="I can answer this.",
                        content=None,
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(reasoning_content=None, content=None),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    cold = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"can_answer": true, "answer_text": "from cold"}',
                    reasoning_content=None,
                    tool_calls=None,
                ),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=2, total_tokens=4),
    )

    mock = AsyncMock(side_effect=[stream_think_only(), cold])
    with patch.object(chat, "_acompletion", new=mock):
        result = await chat.generate_structured(
            (ChatMessage(role="user", content="q"),),
            _TinyResult,
            thinking=ThinkingCallbacks(on_delta=_collect_deltas, on_seconds=lambda _: None),
        )
    assert result.value.answer_text == "from cold"
    assert mock.await_count == 2
