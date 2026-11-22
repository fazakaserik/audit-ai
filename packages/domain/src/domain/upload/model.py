"""Upload and upload-item entities."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, NewType

from pydantic import BaseModel, Field

from domain.common import MODEL_CONFIG
from domain.document import DocumentPath, FolderPath
from domain.engagement import EngagementId

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
    created_at: datetime
    updated_at: datetime
