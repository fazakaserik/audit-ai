"""Engagement value validators."""

from __future__ import annotations

import re

_ENGAGEMENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


def validate_engagement_id(value: str) -> str:
    if not _ENGAGEMENT_ID_RE.fullmatch(value):
        msg = (
            "engagement id must be 2-63 chars, start with a-z0-9, "
            "and contain only a-z0-9-"
        )
        raise ValueError(msg)
    return value
