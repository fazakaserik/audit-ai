"""Fail-closed representation limit tests for parse / ingest."""

from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfWriter

from backend.config import Settings
from backend.domain.errors import RepresentationLimitExceededError
from backend.infrastructure.parsing.parsers.default import parse_bytes
from backend.infrastructure.parsing.parsers.pdf import parse_pdf


def _blank_pdf(pages: int) -> bytes:
    buffer = BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_over_page_limit_raises() -> None:
    data = _blank_pdf(3)
    with pytest.raises(RepresentationLimitExceededError, match="max pages"):
        parse_pdf(data, max_pages=2)


def test_text_over_char_limit_raises() -> None:
    payload = ("x" * 50).encode("utf-8")
    with pytest.raises(RepresentationLimitExceededError, match="max expanded chars"):
        parse_bytes(payload, path="notes/big.txt", max_expanded_chars=20)


def test_under_limits_ok() -> None:
    doc = parse_bytes(
        b"short note",
        path="notes/ok.txt",
        max_expanded_chars=100,
    )
    assert len(doc.sections) == 1


def test_settings_defaults_include_representation_fields() -> None:
    settings = Settings()
    assert settings.ingest_max_pages >= 1
    assert settings.ingest_max_expanded_chars >= 1_000
    assert settings.ingest_max_chunks >= 1
