"""Protocols for Ollama AsyncClient.chat overloads (SDK stubs are partial)."""

from __future__ import annotations

from typing import Protocol, cast

from ollama import AsyncClient


class OllamaChatClient(Protocol):
    async def chat(
        self,
        *,
        model: str,
        messages: object,
        format: object | None = ...,
        tools: object | None = ...,
        think: bool = ...,
        stream: bool = ...,
        options: dict[str, object] | None = ...,
    ) -> object: ...


def ollama_chat_client(client: AsyncClient) -> OllamaChatClient:
    return cast(OllamaChatClient, client)
