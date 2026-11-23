"""Default DocumentParser adapter dispatching by content type."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import assert_never

from backend.application.dto import ParsedDocument
from backend.application.parsing.document_parser import DocumentParser
from backend.domain.document import ContentType
from backend.domain.errors import UnsafeUploadError
from backend.infrastructure.parsing.parsers.markdown import parse_markdown
from backend.infrastructure.parsing.parsers.pdf import parse_pdf
from backend.infrastructure.parsing.parsers.text import parse_text

_EXTENSION_TO_CONTENT_TYPE: dict[str, ContentType] = {
    ".md": ContentType.MARKDOWN,
    ".markdown": ContentType.MARKDOWN,
    ".txt": ContentType.TEXT,
    ".pdf": ContentType.PDF,
}


def detect_content_type(path: str) -> ContentType | None:
    suffix = PurePosixPath(path.replace("\\", "/")).suffix.lower()
    return _EXTENSION_TO_CONTENT_TYPE.get(suffix)


def parse_bytes(data: bytes, *, path: str) -> ParsedDocument:
    content_type = detect_content_type(path)
    if content_type is None:
        raise UnsafeUploadError(f"unsupported document extension for path: {path}")

    match content_type:
        case ContentType.MARKDOWN:
            sections = parse_markdown(data)
        case ContentType.TEXT:
            sections = parse_text(data)
        case ContentType.PDF:
            sections = parse_pdf(data)
        case _:
            assert_never(content_type)

    return ParsedDocument(content_type=content_type, sections=sections)


class DefaultDocumentParser:
    """Infrastructure adapter for DocumentParser."""

    def detect_content_type(self, path: str) -> ContentType | None:
        return detect_content_type(path)

    def parse_bytes(self, data: bytes, *, path: str) -> ParsedDocument:
        return parse_bytes(data, path=path)


def build_document_parser() -> DocumentParser:
    return DefaultDocumentParser()
