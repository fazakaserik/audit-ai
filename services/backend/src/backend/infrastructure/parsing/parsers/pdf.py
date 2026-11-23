"""PDF document parser (pypdf page split + MarkItDown).

pypdf splits the file so each section keeps a real page number for citations.
MarkItDown converts each page to Markdown.
"""

from __future__ import annotations

import io
from collections.abc import Iterator

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from backend.application.dto import ParsedSection
from backend.domain.errors import ValidationError
from backend.infrastructure.parsing.parsers.markdown import parse_markdown
from backend.infrastructure.parsing.parsers.markitdown_convert import convert_to_markdown


def iter_pdf_page_bytes(data: bytes) -> Iterator[tuple[int, bytes]]:
    """Yield (1-based page number, single-page PDF bytes)."""
    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError as exc:
        raise ValidationError("PDF could not be read") from exc

    for page_number, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        buffer = io.BytesIO()
        writer.write(buffer)
        yield page_number, buffer.getvalue()


def pdf_to_markdown(data: bytes) -> str:
    """Convert a PDF to Markdown with ``## Page N`` section markers."""
    parts: list[str] = []
    for page_number, page_bytes in iter_pdf_page_bytes(data):
        markdown = convert_to_markdown(page_bytes, file_extension=".pdf")
        if markdown:
            parts.append(f"## Page {page_number}\n\n{markdown}")
    return "\n\n".join(parts)


def parse_pdf(data: bytes) -> tuple[ParsedSection, ...]:
    sections: list[ParsedSection] = []
    for page_number, page_bytes in iter_pdf_page_bytes(data):
        markdown = convert_to_markdown(page_bytes, file_extension=".pdf")
        if not markdown:
            sections.append(
                ParsedSection(text="", heading_path=(), page=page_number),
            )
            continue
        for section in parse_markdown(markdown.encode("utf-8")):
            sections.append(
                ParsedSection(
                    text=section.text,
                    heading_path=section.heading_path,
                    page=page_number,
                ),
            )
    return tuple(sections)
