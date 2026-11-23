"""Document parsing, chunking, and archive extraction ports."""

from __future__ import annotations

from typing import Protocol

from backend.application.dto import ParsedChunk, ParsedDocument
from backend.domain.document import ContentType


class DocumentParser(Protocol):
    def detect_content_type(self, path: str) -> ContentType | None: ...

    def parse_bytes(self, data: bytes, *, path: str) -> ParsedDocument: ...


class DocumentChunker(Protocol):
    def chunk_document(
        self,
        parsed: ParsedDocument,
        *,
        target_tokens: int = 500,
        overlap_ratio: float = 0.15,
    ) -> list[ParsedChunk]: ...


class ArchiveExtractor(Protocol):
    def is_zip_upload(self, *, filename: str, data: bytes) -> bool: ...

    def list_zip_member_paths(self, data: bytes) -> tuple[str, ...]: ...

    def extract_zip_files(self, data: bytes) -> list[tuple[str, bytes]]: ...
