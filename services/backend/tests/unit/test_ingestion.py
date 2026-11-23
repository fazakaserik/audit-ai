"""Unit tests for ingestion parsers and chunking."""

from __future__ import annotations

import itertools
import zipfile
from io import BytesIO

import pytest
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches
from pypdf import PdfWriter

from backend.application.dto import ParsedDocument, ParsedSection
from backend.domain.document import ContentType
from backend.domain.errors import UnsafeUploadError
from backend.infrastructure.parsing.chunking import chunk_document
from backend.infrastructure.parsing.parsers.default import (
    detect_content_type,
    parse_bytes,
    to_markdown,
)


def _minimal_docx(paragraph: str) -> bytes:
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p></w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
    return buf.getvalue()


def _minimal_xlsx(*, cell_a1: str, cell_b1: int) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet["A1"] = cell_a1
    sheet["B1"] = cell_b1
    buf = BytesIO()
    workbook.save(buf)
    return buf.getvalue()


def _minimal_pptx(text: str) -> bytes:
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
    box.text_frame.text = text
    buf = BytesIO()
    presentation.save(buf)
    return buf.getvalue()


def test_detect_content_type_by_extension() -> None:
    assert detect_content_type("notes/readme.md") == ContentType.MARKDOWN
    assert detect_content_type("notes/readme.markdown") == ContentType.MARKDOWN
    assert detect_content_type("notes/readme.txt") == ContentType.TEXT
    assert detect_content_type("notes/readme.pdf") == ContentType.PDF
    assert detect_content_type("notes/readme.docx") == ContentType.DOCX
    assert detect_content_type("notes/readme.xlsx") == ContentType.XLSX
    assert detect_content_type("notes/readme.pptx") == ContentType.PPTX
    assert detect_content_type("notes/readme.html") == ContentType.HTML
    assert detect_content_type("notes/readme.htm") == ContentType.HTML
    assert detect_content_type("notes/readme.csv") == ContentType.CSV
    assert detect_content_type("notes/readme.exe") is None


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


def _pdf_with_text(line: str) -> bytes:
    """Minimal one-page PDF with selectable Helvetica text."""
    stream = f"BT /F1 24 Tf 50 70 Td ({line}) Tj ET".encode("ascii")
    # Object offsets are approximate; pdfminer tolerates xref noise for this fixture.
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
        b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
        b"4 0 obj<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>stream\n"
        + stream
        + b"\nendstream\nendobj\n"
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"0000000371 00000 n \n"
        b"trailer<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n444\n%%EOF\n"
    )


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


def test_pdf_markitdown_extracts_text() -> None:
    doc = parse_bytes(_pdf_with_text("Payment terms"), path="contracts/terms.pdf")
    assert doc.content_type == ContentType.PDF
    assert len(doc.sections) == 1
    assert doc.sections[0].page == 1
    assert "Payment terms" in doc.sections[0].text


def test_to_markdown_pdf_docx_html() -> None:
    pdf_md = to_markdown(_pdf_with_text("Audit clause"), path="contracts/a.pdf")
    assert "## Page 1" in pdf_md
    assert "Audit clause" in pdf_md

    docx_md = to_markdown(
        _minimal_docx("Payment terms 30 days"),
        path="contracts/terms.docx",
    )
    assert "Payment terms 30 days" in docx_md

    html_md = to_markdown(
        b"<html><body><h1>Hello</h1><p>World audit note</p></body></html>",
        path="policies/note.html",
    )
    assert "Hello" in html_md
    assert "World audit note" in html_md


def test_markitdown_docx_xlsx_pptx_html_csv() -> None:
    docx = parse_bytes(
        _minimal_docx("Payment terms 30 days"),
        path="contracts/terms.docx",
    )
    assert docx.content_type == ContentType.DOCX
    assert any("Payment terms 30 days" in section.text for section in docx.sections)
    assert all(section.page is None for section in docx.sections)

    xlsx = parse_bytes(
        _minimal_xlsx(cell_a1="Revenue", cell_b1=100),
        path="finance/ledger.xlsx",
    )
    assert xlsx.content_type == ContentType.XLSX
    joined_xlsx = "\n".join(section.text for section in xlsx.sections)
    assert "Revenue" in joined_xlsx
    assert "100" in joined_xlsx

    pptx = parse_bytes(
        _minimal_pptx("Audit findings summary"),
        path="meetings/q1.pptx",
    )
    assert pptx.content_type == ContentType.PPTX
    joined_pptx = "\n".join(section.text for section in pptx.sections)
    assert "Audit findings summary" in joined_pptx

    html = parse_bytes(
        b"<html><body><h1>Hello</h1><p>World audit note</p></body></html>",
        path="policies/note.html",
    )
    assert html.content_type == ContentType.HTML
    assert html.sections
    assert html.sections[0].heading_path == ("Hello",)
    assert "World audit note" in html.sections[0].text

    csv = parse_bytes(b"a,b\n1,2\n", path="exports/rows.csv")
    assert csv.content_type == ContentType.CSV
    joined_csv = "\n".join(section.text for section in csv.sections)
    assert "a" in joined_csv and "1" in joined_csv


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

    for left, right in itertools.pairwise(chunks):
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
