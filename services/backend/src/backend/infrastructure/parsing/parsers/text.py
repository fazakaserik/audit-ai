"""Plain text document parser."""

from __future__ import annotations

import re

from backend.application.dto import ParsedSection
from backend.infrastructure.parsing.parsers._decode import decode_text


def parse_text(data: bytes) -> tuple[ParsedSection, ...]:
    text = decode_text(data)
    stripped = text.strip()
    if not stripped:
        return ()

    blocks = [block.strip() for block in re.split(r"\n\s*\n", stripped) if block.strip()]
    if len(blocks) <= 1:
        return (ParsedSection(text=stripped, heading_path=(), page=None),)

    return tuple(ParsedSection(text=block, heading_path=(), page=None) for block in blocks)
