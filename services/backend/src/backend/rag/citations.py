"""Post-filter inline citation markers and build domain Citation objects."""

from __future__ import annotations

import re
from collections.abc import Sequence

from backend.application.ports import ScoredPassage
from domain.answer import Citation

_MARKER_RE = re.compile(r"\[(\d+)\]")
_SNIPPET_MAX = 500


def filter_and_build_citations(
    answer_text: str,
    scored: Sequence[ScoredPassage],
) -> tuple[str, tuple[Citation, ...]] | None:
    """Keep only markers that reference retrieved passages, renumber, build citations."""
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
        passage = row.passage
        snippet = passage.text[:_SNIPPET_MAX]
        citations.append(
            Citation(
                marker=new_marker,
                passage_id=passage.id,
                document_id=passage.document_id,
                document_path=row.document_path,
                page=passage.page,
                heading_path=passage.heading_path,
                snippet=snippet,
                score=row.score,
            )
        )

    return filtered_text, tuple(citations)