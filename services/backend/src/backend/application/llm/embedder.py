"""Embedder protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from backend.application.dto import EmbedResult


class Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> EmbedResult: ...

    @property
    def model_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...
