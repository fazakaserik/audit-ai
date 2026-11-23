"""Post-filter inline citation markers and build domain Citation objects."""

from __future__ import annotations

import re
from collections.abc import Sequence

from backend.application.dto import ScoredChunk
from backend.domain.answer import Citation

_MARKER_RE = re.compile(r"\[(\d+)\]")
_SNIPPET_MAX = 500


def filter_and_build_citations(
    answer_text: str,
    scored: Sequence[ScoredChunk],
) -> tuple[str, tuple[Citation, ...]] | None:
    """Keep only markers that reference retrieved chunks, renumber, build citations."""
    if not scored:
        return None

    max_index = len(scored)
    seen_in_text: list[int] = []
    for match in _MARKER_RE.finditer(answer_text):
        index = int(match.group(1))
        if 1 <= index <= max_index and index not in seen_in_text:
            seen_in_text.append(index)

    if not seen_in_text:
        return None

    old_to_new = {old: new for new, old in enumerate(seen_in_text, start=1)}

    def _replace(match: re.Match[str]) -> str:
        index = int(match.group(1))
        new_marker = old_to_new.get(index)
        if new_marker is None:
            return ""
        return f"[{new_marker}]"

    filtered_text = _MARKER_RE.sub(_replace, answer_text)
    filtered_text = re.sub(r" {2,}", " ", filtered_text).strip()
    if not filtered_text:
        return None

    citations: list[Citation] = []
    for new_marker, old_index in enumerate(seen_in_text, start=1):
        row = scored[old_index - 1]
        chunk = row.chunk
        snippet = chunk.text[:_SNIPPET_MAX]
        citations.append(
            Citation(
                marker=new_marker,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_path=row.document_path,
                page=chunk.page,
                heading_path=chunk.heading_path,
                snippet=snippet,
                score=row.score,
            )
        )

    return filtered_text, tuple(citations)
