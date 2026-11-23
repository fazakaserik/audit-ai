"""Markdown document parser."""

from __future__ import annotations

import re

from backend.application.dto import ParsedSection
from backend.infrastructure.parsing.parsers._decode import decode_text

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def parse_markdown(data: bytes) -> tuple[ParsedSection, ...]:
    text = decode_text(data)
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        body = text.strip()
        if not body:
            return ()
        return (ParsedSection(text=body, heading_path=(), page=None),)

    sections: list[ParsedSection] = []
    heading_titles: list[str] = []
    heading_levels: list[int] = []

    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        while heading_levels and heading_levels[-1] >= level:
            heading_levels.pop()
            heading_titles.pop()
        heading_levels.append(level)
        heading_titles.append(title)
        heading_path = tuple(heading_titles)

        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append(
                ParsedSection(text=body, heading_path=heading_path, page=None),
            )

    return tuple(sections)
