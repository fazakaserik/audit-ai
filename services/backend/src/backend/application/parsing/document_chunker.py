"""Document chunker protocol."""

from __future__ import annotations

from typing import Protocol

from backend.application.dto import ParsedChunk, ParsedDocument


class DocumentChunker(Protocol):
    def chunk_document(
        self,
        parsed: ParsedDocument,
        *,
        target_tokens: int = 500,
        overlap_ratio: float = 0.15,
    ) -> list[ParsedChunk]: ...
