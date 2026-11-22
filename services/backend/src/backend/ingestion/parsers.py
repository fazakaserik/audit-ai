"""Markdown, plain text, and PDF parsers for ingestion."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import assert_never

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from domain.document import ContentType
from domain.errors import UnsafeUploadError, ValidationError

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

_EXTENSION_TO_CONTENT_TYPE: dict[str, ContentType] = {
    ".md": ContentType.MARKDOWN,
    ".markdown": ContentType.MARKDOWN,
    ".txt": ContentType.TEXT,
    ".pdf": ContentType.PDF,
}


@dataclass(frozen=True, slots=True)
class ParsedSection:
    text: str
    heading_path: tuple[str, ...]
    page: int | None


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    content_type: ContentType
    sections: tuple[ParsedSection, ...]


def detect_content_type(path: str) -> ContentType | None:
    suffix = PurePosixPath(path.replace("\\", "/")).suffix.lower()
    return _EXTENSION_TO_CONTENT_TYPE.get(suffix)


def parse_bytes(data: bytes, *, path: str) -> ParsedDocument:
    content_type = detect_content_type(path)
    if content_type is None:
        raise UnsafeUploadError(f"unsupported document extension for path: {path}")

    match content_type:
        case ContentType.MARKDOWN:
            sections = _parse_markdown(data)
        case ContentType.TEXT:
            sections = _parse_text(data)
        case ContentType.PDF:
            sections = _parse_pdf(data)
        case unreachable:
            assert_never(unreachable)

    return ParsedDocument(content_type=content_type, sections=sections)


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("document must be valid UTF-8 text") from exc


def _parse_markdown(data: bytes) -> tuple[ParsedSection, ...]:
    text = _decode_text(data)
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        body = text.strip()
        if not body:
            return ()
        return (ParsedSection(text=body, heading_path=(), page=None),)

    sections: list[ParsedSection] = []
    heading_titles: list[str] = []

    prelude = text[: matches[0].start()].strip()
    if prelude:
        sections.append(ParsedSection(text=prelude, heading_path=(), page=None))

    for idx, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        if level > len(heading_titles):
            heading_titles.extend([""] * (level - len(heading_titles)))
        heading_titles = heading_titles[:level]
        heading_titles[level - 1] = title
        heading_titles = heading_titles[:level]
        heading_path = tuple(t for t in heading_titles if t)

        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        if body:
            sections.append(
                ParsedSection(text=body, heading_path=heading_path, page=None),
            )

    return tuple(sections)


def _parse_text(data: bytes) -> tuple[ParsedSection, ...]:
    text = _decode_text(data)
    stripped = text.strip()
    if not stripped:
        return ()

    blocks = [block.strip() for block in re.split(r"\n\s*\n", stripped) if block.strip()]
    if len(blocks) <= 1:
        return (ParsedSection(text=stripped, heading_path=(), page=None),)

    return tuple(
        ParsedSection(text=block, heading_path=(), page=None) for block in blocks
    )


def _parse_pdf(data: bytes) -> tuple[ParsedSection, ...]:
    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError as exc:
        raise ValidationError("PDF could not be read") from exc

    sections: list[ParsedSection] = []
    for page_number, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        normalized = raw.strip()
        heading_path: tuple[str, ...] = ()
        if normalized:
            first_line = normalized.splitlines()[0].strip()
            if first_line:
                heading_path = (first_line,)
        sections.append(
            ParsedSection(
                text=normalized,
                heading_path=heading_path,
                page=page_number,
            ),
        )

    return tuple(sections)