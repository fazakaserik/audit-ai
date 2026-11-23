"""Shared UTF-8 decode helper for text-based parsers."""

from __future__ import annotations

from backend.domain.errors import ValidationError


def decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("document must be valid UTF-8 text") from exc
