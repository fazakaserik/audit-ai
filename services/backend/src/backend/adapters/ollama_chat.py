"""Ollama ChatModel adapter (structured JSON via format=schema)."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Sequence
from typing import Any, TypeVar, cast

import httpx
from ollama import AsyncClient, ResponseError
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt

from backend.adapters._retry import MAX_ATTEMPTS, RETRY_WAIT
from backend.application.ports import ChatMessage, StructuredResult, ThinkingCallbacks
from domain.errors import ModelTimeoutError, ModelUnavailableError
from domain.session import LlmUsage


def _usage_from_ollama(response: object) -> LlmUsage:
    prompt = getattr(response, "prompt_eval_count", None)
    completion = getattr(response, "eval_count", None)
    return LlmUsage.from_counts(prompt_tokens=prompt, completion_tokens=completion)

TModel = TypeVar("TModel", bound=BaseModel)

_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, ResponseError) and (exc.status_code >= 500 or exc.status_code == 429):
        return True
    return False


def _extract_json_text(*, content: str | None, thinking: str | None) -> str:
    """Prefer message content; fall back to JSON embedded in thinking (Qwen-style)."""
    for candidate in (content, thinking):
        if candidate is None:
            continue
        text = candidate.strip()
        if not text:
            continue
        try:
            json.loads(text)
        except json.JSONDecodeError:
            match = _JSON_OBJECT_RE.search(text)
            if match is None:
                continue
            text = match.group(0)
            try:
                json.loads(text)
            except json.JSONDecodeError:
                continue
        return text
    raise ModelUnavailableError("Ollama chat returned empty content")


class OllamaChatModel:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_concurrent_calls: int,
        supports_thinking: bool | None = None,
    ) -> None:
        self._model = model
        self._semaphore = asyncio.Semaphore(max_concurrent_calls)
        self._client = AsyncClient(host=base_url, timeout=timeout_seconds)
        self._supports_thinking = supports_thinking if supports_thinking is not None else False
        self._thinking_probed = supports_thinking is not None

    @property
    def supports_thinking(self) -> bool:
        return self._supports_thinking

    async def _ensure_thinking_capability(self) -> None:
        if self._thinking_probed:
            return
        self._thinking_probed = True
        try:
            shown = await self._client.show(self._model)
        except Exception:
            self._supports_thinking = False
            return
        caps = getattr(shown, "capabilities", None)
        if isinstance(caps, list):
            self._supports_thinking = "thinking" in caps
        else:
            self._supports_thinking = False

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> StructuredResult[TModel]:
        async with self._semaphore:
            try:
                return await self._generate_structured_once(messages, schema, thinking=thinking)
            except (httpx.TimeoutException, TimeoutError) as exc:
                raise ModelTimeoutError("Ollama chat request timed out") from exc
            except (ConnectionError, ResponseError, ValidationError) as exc:
                raise ModelUnavailableError("Ollama chat request failed") from exc

    @retry(
        reraise=True,
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=RETRY_WAIT,
        retry=retry_if_exception(_is_transient),
    )
    async def _generate_structured_once(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
        *,
        thinking: ThinkingCallbacks | None,
    ) -> StructuredResult[TModel]:
        await self._ensure_thinking_capability()
        vendor_messages = [
            {"role": message.role, "content": message.content} for message in messages
        ]
        format_schema: dict[str, Any] = schema.model_json_schema()
        use_think = self._supports_thinking

        if thinking is not None and use_think:
            started = time.perf_counter()
            content_parts: list[str] = []
            thinking_parts: list[str] = []
            usage = LlmUsage()
            stream = await self._client.chat(
                model=self._model,
                messages=cast(Any, vendor_messages),
                format=format_schema,
                think=True,
                stream=True,
                options={"temperature": 0},
            )
            async for chunk in stream:
                if getattr(chunk, "done", False):
                    usage = _usage_from_ollama(chunk)
                message = chunk.message
                delta_thinking = getattr(message, "thinking", None)
                if isinstance(delta_thinking, str) and delta_thinking:
                    thinking_parts.append(delta_thinking)
                    await thinking.on_delta(delta_thinking)
                delta_content = message.content
                if isinstance(delta_content, str) and delta_content:
                    content_parts.append(delta_content)
            thinking.on_seconds(time.perf_counter() - started)
            payload = _extract_json_text(
                content="".join(content_parts) or None,
                thinking="".join(thinking_parts) or None,
            )
            return StructuredResult(value=schema.model_validate_json(payload), usage=usage)

        response = await self._client.chat(
            model=self._model,
            messages=cast(Any, vendor_messages),
            format=format_schema,
            think=use_think,
            options={"temperature": 0},
        )
        payload = _extract_json_text(
            content=response.message.content,
            thinking=getattr(response.message, "thinking", None),
        )
        return StructuredResult(
            value=schema.model_validate_json(payload),
            usage=_usage_from_ollama(response),
        )
