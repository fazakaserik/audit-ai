"""Default DocumentParser adapter dispatching by content type."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import assert_never

from backend.application.dto import ParsedDocument
from backend.application.parsing.document_parser import DocumentParser
from backend.domain.document import ContentType
from backend.domain.errors import UnsafeUploadError
from backend.infrastructure.parsing.parsers._decode import decode_text
from backend.infrastructure.parsing.parsers.markdown import parse_markdown
from backend.infrastructure.parsing.parsers.markitdown_convert import (
    convert_to_markdown,
    parse_via_markitdown,
)
from backend.infrastructure.parsing.parsers.pdf import parse_pdf, pdf_to_markdown
from backend.infrastructure.parsing.parsers.text import parse_text

_EXTENSION_TO_CONTENT_TYPE: dict[str, ContentType] = {
    ".md": ContentType.MARKDOWN,
    ".markdown": ContentType.MARKDOWN,
    ".txt": ContentType.TEXT,
    ".pdf": ContentType.PDF,
    ".docx": ContentType.DOCX,
    ".xlsx": ContentType.XLSX,
    ".pptx": ContentType.PPTX,
    ".html": ContentType.HTML,
    ".htm": ContentType.HTML,
    ".csv": ContentType.CSV,
}


def detect_content_type(path: str) -> ContentType | None:
    suffix = PurePosixPath(path.replace("\\", "/")).suffix.lower()
    return _EXTENSION_TO_CONTENT_TYPE.get(suffix)


def parse_bytes(data: bytes, *, path: str) -> ParsedDocument:
    content_type = detect_content_type(path)
    if content_type is None:
        raise UnsafeUploadError(f"unsupported document extension for path: {path}")

    suffix = PurePosixPath(path.replace("\\", "/")).suffix.lower() or None

    match content_type:
        case ContentType.MARKDOWN:
            sections = parse_markdown(data)
        case ContentType.TEXT:
            sections = parse_text(data)
        case ContentType.PDF:
            # MarkItDown per page (via pypdf split) so sections keep page numbers.
            sections = parse_pdf(data)
        case (
            ContentType.DOCX
            | ContentType.XLSX
            | ContentType.PPTX
            | ContentType.HTML
            | ContentType.CSV
        ):
            if suffix is None:
                raise UnsafeUploadError(f"unsupported document extension for path: {path}")
            sections = parse_via_markitdown(data, file_extension=suffix)
        case _:
            assert_never(content_type)

    return ParsedDocument(content_type=content_type, sections=sections)


def to_markdown(data: bytes, *, path: str) -> str:
    """Convert stored document bytes to Markdown for viewing."""
    content_type = detect_content_type(path)
    if content_type is None:
        raise UnsafeUploadError(f"unsupported document extension for path: {path}")

    suffix = PurePosixPath(path.replace("\\", "/")).suffix.lower() or None

    match content_type:
        case ContentType.MARKDOWN | ContentType.TEXT:
            return decode_text(data)
        case ContentType.PDF:
            return pdf_to_markdown(data)
        case (
            ContentType.DOCX
            | ContentType.XLSX
            | ContentType.PPTX
            | ContentType.HTML
            | ContentType.CSV
        ):
            if suffix is None:
                raise UnsafeUploadError(f"unsupported document extension for path: {path}")
            return convert_to_markdown(data, file_extension=suffix)
        case _:
            assert_never(content_type)


class DefaultDocumentParser:
    """Infrastructure adapter for DocumentParser."""

    def detect_content_type(self, path: str) -> ContentType | None:
        return detect_content_type(path)

    def parse_bytes(self, data: bytes, *, path: str) -> ParsedDocument:
        return parse_bytes(data, path=path)

    def to_markdown(self, data: bytes, *, path: str) -> str:
        return to_markdown(data, path=path)


def build_document_parser() -> DocumentParser:
    return DefaultDocumentParser()
