"""Document path validators."""

from __future__ import annotations

import re

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def normalize_posix_path(value: str, *, allow_empty: bool) -> str:
    raw = value.replace("\\", "/")
    if _CONTROL_CHARS_RE.search(raw):
        raise ValueError("path must not contain control characters")
    if raw.startswith("/") or re.match(r"^[a-zA-Z]:", raw):
        raise ValueError("path must be relative")
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if ".." in parts:
        raise ValueError("path must not contain '..'")
    if not parts:
        if allow_empty:
            return ""
        raise ValueError("path must not be empty")
    return "/".join(parts)


def validate_folder_path(value: str) -> str:
    return normalize_posix_path(value, allow_empty=True)


def validate_document_path(value: str) -> str:
    path = normalize_posix_path(value, allow_empty=False)
    name = path.rsplit("/", 1)[-1]
    if "." not in name or name.startswith(".") or name.endswith("."):
        raise ValueError("document path must end with a filename that has an extension")
    return path
