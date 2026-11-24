"""Extract a JSON object from model content or thinking prose."""

from __future__ import annotations

import json

from backend.domain.errors import ModelUnavailableError


def try_parse_json_object(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        json.loads(stripped)
        return stripped
    except json.JSONDecodeError:
        pass
    # Prefer the last object — thinking prose often has braces before the payload.
    decoder = json.JSONDecoder()
    last: str | None = None
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            value, end = decoder.raw_decode(stripped, index)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            last = stripped[index:end]
    return last


def extract_json_text(*, content: str | None, thinking: str | None) -> str:
    """Prefer message content; fall back to JSON embedded in thinking (Qwen-style)."""
    for candidate in (content, thinking):
        if candidate is None:
            continue
        parsed = try_parse_json_object(candidate)
        if parsed is not None:
            return parsed
    raise ModelUnavailableError("Chat model returned empty content")
