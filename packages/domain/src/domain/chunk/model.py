"""Chunk entity (searchable document fragment)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, NewType

from pydantic import BaseModel, Field

from domain.common import MODEL_CONFIG
from domain.document import DocumentId

ChunkId = NewType("ChunkId", uuid.UUID)


class Chunk(BaseModel):
    model_config = MODEL_CONFIG

    id: ChunkId
    document_id: DocumentId
    document_version: Annotated[int, Field(ge=1)]
    ordinal: Annotated[int, Field(ge=0)]
    page: Annotated[int, Field(ge=1)] | None = None
    heading_path: tuple[str, ...] = ()
    text: Annotated[str, Field(min_length=1)]
    token_count: Annotated[int, Field(ge=1)]
    created_at: datetime
