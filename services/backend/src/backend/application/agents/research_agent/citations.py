"""Post-filter inline citation markers and build domain Citation objects."""

from __future__ import annotations

import re
from collections.abc import Sequence

from backend.application.dto import ScoredChunk
from backend.domain.answer import Citation

_MARKER_RE = re.compile(r"\[(\d+)\]")
_SNIPPET_MAX = 500


def _valid_markers_in_text(answer_text: str, max_index: int) -> list[int]:
    seen: list[int] = []
    for match in _MARKER_RE.finditer(answer_text):
        index = int(match.group(1))
        if 1 <= index <= max_index and index not in seen:
            seen.append(index)
    return seen


def _ensure_markers(
    answer_text: str,
    *,
    max_index: int,
    markers_used: Sequence[int],
) -> str:
    """If the answer omitted [n] markers, attach ``markers_used`` or a default [1]."""
    if _valid_markers_in_text(answer_text, max_index):
        return answer_text
    salvage = [m for m in markers_used if 1 <= m <= max_index]
    # Preserve order, drop duplicates.
    unique: list[int] = []
    for marker in salvage:
        if marker not in unique:
            unique.append(marker)
    # Grounded answers with evidence must keep a citation (FR-016a) — default to [1]
    # when the model forgot both inline markers and markers_used.
    if not unique and max_index >= 1:
        unique = [1]
    if not unique:
        return answer_text
    suffix = " " + " ".join(f"[{m}]" for m in unique)
    return answer_text.rstrip() + suffix


def filter_and_build_citations(
    answer_text: str,
    scored: Sequence[ScoredChunk],
    *,
    markers_used: Sequence[int] = (),
) -> tuple[str, tuple[Citation, ...]] | None:
    """Keep only markers that reference retrieved chunks, renumber, build citations.

    When the model answers with evidence but forgets inline [n] markers, attach
    ``markers_used`` (or ``[1]``) so a grounded answer is not discarded.
    """
    if not scored:
        return None

    max_index = len(scored)
    text = _ensure_markers(
        answer_text,
        max_index=max_index,
        markers_used=markers_used,
    )
    seen_in_text = _valid_markers_in_text(text, max_index)
    if not seen_in_text:
        return None

    old_to_new = {old: new for new, old in enumerate(seen_in_text, start=1)}

    def _replace(match: re.Match[str]) -> str:
        index = int(match.group(1))
        new_marker = old_to_new.get(index)
        if new_marker is None:
            return ""
        return f"[{new_marker}]"

    filtered_text = _MARKER_RE.sub(_replace, text)
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
