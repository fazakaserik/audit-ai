"""Shared domain primitives used across features."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import NewType

from pydantic import ConfigDict

MODEL_CONFIG = ConfigDict(frozen=True, strict=True, extra="forbid")

RequestId = NewType("RequestId", uuid.UUID)


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()
