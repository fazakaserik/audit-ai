"""Document parser protocol."""

from __future__ import annotations

from typing import Protocol

from backend.application.dto import ParsedDocument
from backend.domain.document import ContentType


class DocumentParser(Protocol):
    def detect_content_type(self, path: str) -> ContentType | None: ...

    def parse_bytes(self, data: bytes, *, path: str) -> ParsedDocument: ...

    def to_markdown(self, data: bytes, *, path: str) -> str: ...
