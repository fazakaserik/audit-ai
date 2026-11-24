"""Default DocumentParser adapter dispatching by content type."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import assert_never

from backend.application.dto import ParsedDocument, ParsedSection
from backend.application.parsing.document_parser import DocumentParser
from backend.domain.document import ContentType
from backend.domain.errors import RepresentationLimitExceededError, UnsafeUploadError
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


def _expanded_char_count(sections: tuple[ParsedSection, ...]) -> int:
    return sum(len(section.text) for section in sections)


def _enforce_expanded_chars(
    sections: tuple[ParsedSection, ...],
    *,
    max_expanded_chars: int | None,
) -> None:
    if max_expanded_chars is None:
        return
    total = _expanded_char_count(sections)
    if total > max_expanded_chars:
        raise RepresentationLimitExceededError(
            f"document exceeds max expanded chars ({max_expanded_chars}): {total}"
        )


def parse_bytes(
    data: bytes,
    *,
    path: str,
    max_pages: int | None = None,
    max_expanded_chars: int | None = None,
) -> ParsedDocument:
    content_type = detect_content_type(path)
    if content_type is None:
        raise UnsafeUploadError(f"unsupported document extension for path: {path}")

    suffix = PurePosixPath(path.replace("\\", "/")).suffix.lower() or None

    match content_type:
        case ContentType.MARKDOWN:
            sections = parse_markdown(data)
            _enforce_expanded_chars(sections, max_expanded_chars=max_expanded_chars)
        case ContentType.TEXT:
            sections = parse_text(data)
            _enforce_expanded_chars(sections, max_expanded_chars=max_expanded_chars)
        case ContentType.PDF:
            # MarkItDown per page (via pypdf split) so sections keep page numbers.
            sections = parse_pdf(data, max_pages=max_pages)
            _enforce_expanded_chars(sections, max_expanded_chars=max_expanded_chars)
        case (
            ContentType.DOCX
            | ContentType.XLSX
            | ContentType.PPTX
            | ContentType.HTML
            | ContentType.CSV
        ):
            if suffix is None:
                raise UnsafeUploadError(f"unsupported document extension for path: {path}")
            sections = parse_via_markitdown(
                data,
                file_extension=suffix,
                max_expanded_chars=max_expanded_chars,
            )
        case _:
            assert_never(content_type)

    return ParsedDocument(content_type=content_type, sections=sections)


def to_markdown(
    data: bytes,
    *,
    path: str,
    max_pages: int | None = None,
    max_expanded_chars: int | None = None,
) -> str:
    """Convert stored document bytes to Markdown for viewing."""
    content_type = detect_content_type(path)
    if content_type is None:
        raise UnsafeUploadError(f"unsupported document extension for path: {path}")

    suffix = PurePosixPath(path.replace("\\", "/")).suffix.lower() or None

    match content_type:
        case ContentType.MARKDOWN | ContentType.TEXT:
            text = decode_text(data)
            if max_expanded_chars is not None and len(text) > max_expanded_chars:
                raise RepresentationLimitExceededError(
                    f"document exceeds max expanded chars ({max_expanded_chars}): {len(text)}"
                )
            return text
        case ContentType.PDF:
            text = pdf_to_markdown(data, max_pages=max_pages)
            if max_expanded_chars is not None and len(text) > max_expanded_chars:
                raise RepresentationLimitExceededError(
                    f"document exceeds max expanded chars ({max_expanded_chars}): {len(text)}"
                )
            return text
        case (
            ContentType.DOCX
            | ContentType.XLSX
            | ContentType.PPTX
            | ContentType.HTML
            | ContentType.CSV
        ):
            if suffix is None:
                raise UnsafeUploadError(f"unsupported document extension for path: {path}")
            return convert_to_markdown(
                data,
                file_extension=suffix,
                max_expanded_chars=max_expanded_chars,
            )
        case _:
            assert_never(content_type)


class DefaultDocumentParser:
    """Infrastructure adapter for DocumentParser."""

    def __init__(
        self,
        *,
        max_pages: int | None = None,
        max_expanded_chars: int | None = None,
    ) -> None:
        self._max_pages = max_pages
        self._max_expanded_chars = max_expanded_chars

    def detect_content_type(self, path: str) -> ContentType | None:
        return detect_content_type(path)

    def parse_bytes(self, data: bytes, *, path: str) -> ParsedDocument:
        return parse_bytes(
            data,
            path=path,
            max_pages=self._max_pages,
            max_expanded_chars=self._max_expanded_chars,
        )

    def to_markdown(self, data: bytes, *, path: str) -> str:
        return to_markdown(
            data,
            path=path,
            max_pages=self._max_pages,
            max_expanded_chars=self._max_expanded_chars,
        )


def build_document_parser(
    *,
    max_pages: int | None = None,
    max_expanded_chars: int | None = None,
) -> DocumentParser:
    return DefaultDocumentParser(
        max_pages=max_pages,
        max_expanded_chars=max_expanded_chars,
    )
