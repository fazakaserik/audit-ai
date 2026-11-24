"""Convert Office/HTML/CSV/PDF page bytes to Markdown via Microsoft MarkItDown.

PDFs are split per page in ``parsers.pdf`` before conversion so citation
metadata can keep a real page number.
"""

from __future__ import annotations

import io
from functools import lru_cache

from markitdown import MarkItDown, MarkItDownException

from backend.application.dto import ParsedSection
from backend.domain.errors import RepresentationLimitExceededError, ValidationError
from backend.infrastructure.parsing.parsers.markdown import parse_markdown


@lru_cache(maxsize=1)
def _markitdown() -> MarkItDown:
    return MarkItDown(enable_plugins=False)


def convert_to_markdown(
    data: bytes,
    *,
    file_extension: str,
    max_expanded_chars: int | None = None,
) -> str:
    """Convert document bytes to Markdown using convert_stream only."""
    extension = file_extension if file_extension.startswith(".") else f".{file_extension}"
    try:
        result = _markitdown().convert_stream(
            io.BytesIO(data),
            file_extension=extension,
        )
    except MarkItDownException as exc:
        raise ValidationError(f"document could not be converted: {exc}") from exc
    except Exception as exc:
        raise ValidationError(f"document could not be converted: {exc}") from exc

    text = (result.text_content or "").strip()
    if max_expanded_chars is not None and len(text) > max_expanded_chars:
        raise RepresentationLimitExceededError(
            f"document exceeds max expanded chars ({max_expanded_chars}): {len(text)}"
        )
    return text


def parse_via_markitdown(
    data: bytes,
    *,
    file_extension: str,
    max_expanded_chars: int | None = None,
) -> tuple[ParsedSection, ...]:
    """Convert to Markdown, then reuse the Markdown section splitter."""
    markdown = convert_to_markdown(
        data,
        file_extension=file_extension,
        max_expanded_chars=max_expanded_chars,
    )
    if not markdown:
        return ()
    return parse_markdown(markdown.encode("utf-8"))
