"""Helpers for folder-prefix document listing."""

from __future__ import annotations


def normalize_list_prefix(prefix: str | None) -> str:
    if prefix is None or prefix == "":
        return ""
    return prefix.rstrip("/")


def relative_segments(path: str, prefix: str) -> list[str] | None:
    """Return path segments under prefix, or None if path is not under prefix."""
    if prefix == "":
        return path.split("/") if path else []
    if not path.startswith(prefix + "/"):
        return None
    relative = path[len(prefix) + 1 :]
    if not relative:
        return []
    return relative.split("/")


def within_depth(segments: list[str], depth: int | None) -> bool:
    if depth is None:
        return True
    return len(segments) <= depth


def child_folder_name(segments: list[str]) -> str | None:
    """Immediate child folder under the listing prefix, if the path is nested."""
    if len(segments) > 1:
        return segments[0]
    return None
