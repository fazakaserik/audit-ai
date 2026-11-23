"""Upload and upload-item entities."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, NewType

from pydantic import BaseModel, Field

from backend.domain.common import MODEL_CONFIG
from backend.domain.document import DocumentPath, FolderPath
from backend.domain.engagement import EngagementId

UploadId = NewType("UploadId", uuid.UUID)
UploadItemId = NewType("UploadItemId", uuid.UUID)


class UploadStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadItemStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    SKIPPED = "skipped"
    NOT_SEARCHABLE = "not_searchable"
    FAILED = "failed"


class Upload(BaseModel):
    model_config = MODEL_CONFIG

    id: UploadId
    engagement_id: EngagementId
    target_folder: FolderPath
    status: UploadStatus
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UploadItem(BaseModel):
    model_config = MODEL_CONFIG

    id: UploadItemId
    upload_id: UploadId
    document_path: DocumentPath
    status: UploadItemStatus
    reason: str | None = None
    attempts: Annotated[int, Field(ge=0)] = 0
    processing_started_at: datetime | None = None
    processing_finished_at: datetime | None = None
    embedding_prompt_tokens: Annotated[int | None, Field(ge=0)] = None
    embedding_total_tokens: Annotated[int | None, Field(ge=0)] = None
    chunk_count: Annotated[int | None, Field(ge=0)] = None
    chunk_token_sum: Annotated[int | None, Field(ge=0)] = None
    created_at: datetime
    updated_at: datetime

    @property
    def processing_duration_ms(self) -> int | None:
        if self.processing_started_at is None or self.processing_finished_at is None:
            return None
        delta = self.processing_finished_at - self.processing_started_at
        return max(0, int(delta.total_seconds() * 1000))
