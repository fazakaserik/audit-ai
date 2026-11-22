"""Unit tests for ingestion parsers and chunking."""

from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfWriter

from backend.ingestion.chunking import chunk_document
from backend.ingestion.parsers import (
    ParsedDocument,
    ParsedSection,
    detect_content_type,
    parse_bytes,
)
from domain.document import ContentType
from domain.errors import UnsafeUploadError


def test_detect_content_type_by_extension() -> None:
    assert detect_content_type("notes/readme.md") == ContentType.MARKDOWN
    assert detect_content_type("notes/readme.markdown") == ContentType.MARKDOWN
    assert detect_content_type("notes/readme.txt") == ContentType.TEXT
    assert detect_content_type("notes/readme.pdf") == ContentType.PDF
    assert detect_content_type("notes/readme.docx") is None


def test_markdown_heading_paths() -> None:
    source = b"""# Top
intro under top

## Sub
content under sub

# Another
second top-level
"""
    doc = parse_bytes(source, path="policies/risk.md")
    assert doc.content_type == ContentType.MARKDOWN
    assert [s.heading_path for s in doc.sections] == [
        ("Top",),
        ("Top", "Sub"),
        ("Another",),
    ]
    assert [s.page for s in doc.sections] == [None, None, None]
    assert doc.sections[0].text == "intro under top"
    assert doc.sections[1].text == "content under sub"


def test_pdf_page_assignment() -> None:
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)

    doc = parse_bytes(buffer.getvalue(), path="reports/q1.pdf")
    assert doc.content_type == ContentType.PDF
    assert len(doc.sections) == 2
    assert doc.sections[0].page == 1
    assert doc.sections[1].page == 2


def test_chunk_overlap_and_token_bounds() -> None:
    words = " ".join(f"word{i}" for i in range(2_000))
    parsed = ParsedDocument(
        content_type=ContentType.TEXT,
        sections=(ParsedSection(text=words, heading_path=(), page=None),),
    )

    chunks = chunk_document(parsed, target_tokens=100, overlap_ratio=0.15)
    assert len(chunks) > 1
    assert all(1 <= c.token_count <= 100 for c in chunks)
    assert all(c.page is None for c in chunks)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))

    for left, right in zip(chunks[:-1], chunks[1:], strict=True):
        assert left.heading_path == right.heading_path
        assert left.page == right.page


def test_chunk_keeps_distinct_heading_paths_separate() -> None:
    parsed = ParsedDocument(
        content_type=ContentType.MARKDOWN,
        sections=(
            ParsedSection(text="alpha section " * 200, heading_path=("A",), page=None),
            ParsedSection(text="beta section " * 200, heading_path=("B",), page=None),
        ),
    )
    chunks = chunk_document(parsed, target_tokens=50, overlap_ratio=0.15)
    paths = {c.heading_path for c in chunks}
    assert paths == {("A",), ("B",)}


def test_unsupported_extension_raises() -> None:
    with pytest.raises(UnsafeUploadError):
        parse_bytes(b"data", path="file.exe")
