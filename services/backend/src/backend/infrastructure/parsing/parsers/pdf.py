"""PDF document parser."""

from __future__ import annotations

import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from backend.application.dto import ParsedSection
from backend.domain.errors import ValidationError


def parse_pdf(data: bytes) -> tuple[ParsedSection, ...]:
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
