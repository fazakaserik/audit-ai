"""Structured generate: keep reading after thinking budget; cold-retry if no JSON."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, ConfigDict

import backend.infrastructure.ollama_chat as ollama_mod
from backend.application.dto import ChatMessage, ThinkingCallbacks
from backend.infrastructure.ollama_chat import OllamaChatModel


class _TinyResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    can_answer: bool
    answer_text: str = ""


async def _collect_deltas(text: str) -> None:
    _ = text


@pytest.mark.asyncio
async def test_structured_does_not_abort_stream_before_json_content() -> None:
    chat = OllamaChatModel(
        base_url="http://test",
        model="test",
        timeout_seconds=30,
        max_concurrent_calls=1,
        supports_thinking=True,
    )

    async def stream_think_then_json() -> Any:
        yield SimpleNamespace(
            done=False,
            message=SimpleNamespace(thinking="x" * 100, content=""),
        )
        yield SimpleNamespace(
            done=False,
            message=SimpleNamespace(
                thinking="",
                content='{"can_answer": true, "answer_text": "yes"}',
            ),
        )
        yield SimpleNamespace(
            done=True,
            message=SimpleNamespace(thinking=None, content=""),
            prompt_eval_count=1,
            eval_count=1,
        )

    chat._client.chat = AsyncMock(side_effect=[stream_think_then_json()])
    original_chars = ollama_mod._THINKING_BUDGET_CHARS
    ollama_mod._THINKING_BUDGET_CHARS = 10
    try:
        result = await chat.generate_structured(
            (ChatMessage(role="user", content="q"),),
            _TinyResult,
            thinking=ThinkingCallbacks(on_delta=_collect_deltas, on_seconds=lambda _: None),
        )
    finally:
        ollama_mod._THINKING_BUDGET_CHARS = original_chars

    assert result.value.can_answer is True
    assert result.value.answer_text == "yes"
    assert chat._client.chat.await_count == 1


@pytest.mark.asyncio
async def test_structured_retries_without_think_when_stream_has_no_json() -> None:
    chat = OllamaChatModel(
        base_url="http://test",
        model="test",
        timeout_seconds=30,
        max_concurrent_calls=1,
        supports_thinking=True,
    )

    async def stream_think_only() -> Any:
        yield SimpleNamespace(
            done=False,
            message=SimpleNamespace(thinking="I can answer this.", content=""),
        )
        yield SimpleNamespace(
            done=True,
            message=SimpleNamespace(thinking=None, content=""),
            prompt_eval_count=1,
            eval_count=1,
        )

    cold = SimpleNamespace(
        message=SimpleNamespace(
            content='{"can_answer": true, "answer_text": "from cold"}',
            thinking=None,
        ),
        prompt_eval_count=2,
        eval_count=2,
    )

    chat._client.chat = AsyncMock(side_effect=[stream_think_only(), cold])
    result = await chat.generate_structured(
        (ChatMessage(role="user", content="q"),),
        _TinyResult,
        thinking=ThinkingCallbacks(on_delta=_collect_deltas, on_seconds=lambda _: None),
    )
    assert result.value.answer_text == "from cold"
    assert chat._client.chat.await_count == 2
