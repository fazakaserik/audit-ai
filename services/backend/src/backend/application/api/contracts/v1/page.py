"""Offset-based pagination wrapper."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Page[T](BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    items: tuple[T, ...]
    total: Annotated[int, Field(ge=0)]
    limit: Annotated[int, Field(ge=1, le=200)]
    offset: Annotated[int, Field(ge=0)]
