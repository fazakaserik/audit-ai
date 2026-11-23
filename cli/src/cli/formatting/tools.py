"""Tool argument parsing and progress detail helpers."""

from __future__ import annotations

import json
import re
from typing import cast

from cli.formatting.labels import tool_label

TOOL_DETAIL_MAX = 72
SOURCE_PATHS_MAX = 5
_RESULT_ARROW_RE = re.compile(r"^.*→\s*")


def truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return "…"
    return text[: max_len - 1].rstrip() + "…"


def parse_tool_args(arguments: str) -> dict[str, object]:
    raw = arguments.strip()
    if not raw:
        return {}
    try:
        parsed_raw = cast(object, json.loads(raw))
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed_raw, dict):
        return {}
    return cast(dict[str, object], parsed_raw)


def tool_detail(name: str, arguments: str) -> str:
    args = parse_tool_args(arguments)
    if name == "search_relevant_chunks":
        query = args.get("query")
        if isinstance(query, str) and query.strip():
            return f"“{truncate(query.strip(), TOOL_DETAIL_MAX)}”"
    elif name == "read_document":
        path = args.get("path")
        if isinstance(path, str) and path.strip():
            return truncate(path.strip(), TOOL_DETAIL_MAX)
    elif name == "list_documents":
        prefix = args.get("prefix")
        if isinstance(prefix, str) and prefix.strip():
            return truncate(prefix.strip(), TOOL_DETAIL_MAX)
        return "/"
    if args:
        compact = json.dumps(args, ensure_ascii=False, separators=(",", ":"))
        return truncate(compact, TOOL_DETAIL_MAX)
    stripped = arguments.strip()
    return truncate(stripped, TOOL_DETAIL_MAX) if stripped else ""


def dedupe_sources_by_path(
    sources: list[dict[str, object]],
) -> list[tuple[str, float | None]]:
    best: dict[str, float | None] = {}
    order: list[str] = []
    for item in sources:
        path = str(item.get("path", "")).strip()
        if not path:
            continue
        score_raw = item.get("score")
        score: float | None = float(score_raw) if isinstance(score_raw, (int, float)) else None
        if path not in best:
            order.append(path)
            best[path] = score
            continue
        previous = best[path]
        if score is not None and (previous is None or score > previous):
            best[path] = score
    ranked = [(path, best[path]) for path in order]
    ranked.sort(
        key=lambda row: (-row[1] if row[1] is not None else float("inf"), row[0]),
    )
    return ranked


def short_tool_result(name: str, summary: str) -> str:
    text = summary.strip()
    if not text:
        return ""
    if text.startswith(name):
        text = _RESULT_ARROW_RE.sub("", text).strip()
    elif "→" in text:
        text = text.split("→", 1)[1].strip()
    return text


def tool_call_line(*, name: str, arguments: str) -> str:
    label = tool_label(name)
    detail = tool_detail(name, arguments)
    return f"▸ {label}" if not detail else f"▸ {label}  {detail}"


def source_progress_lines(sources: list[dict[str, object]]) -> list[str]:
    """One-shot source listing (legacy smoke / undecorrelated sources events)."""
    if not sources:
        return ["  (no sources)"]
    unique = dedupe_sources_by_path(sources)
    lines: list[str] = []
    shown = unique[:SOURCE_PATHS_MAX]
    for path, score in shown:
        if score is None:
            lines.append(f"  · {path}")
        else:
            lines.append(f"  · {path}  {score:.2f}")
    remaining = len(unique) - len(shown)
    if remaining > 0:
        lines.append(f"  · +{remaining} more")
    return lines
