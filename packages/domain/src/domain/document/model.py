"""Document entity, paths, and content type."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, NewType

from pydantic import AfterValidator, BaseModel, Field

from domain.common import MODEL_CONFIG
from domain.document.validators import validate_document_path, validate_folder_path
from domain.engagement import EngagementId

DocumentId = NewType("DocumentId", uuid.UUID)
FolderPath = Annotated[str, AfterValidator(validate_folder_path)]
DocumentPath = Annotated[str, AfterValidator(validate_document_path)]


class ContentType(StrEnum):
    MARKDOWN = "markdown"
    TEXT = "text"
    PDF = "pdf"


class Document(BaseModel):
    model_config = MODEL_CONFIG

    id: DocumentId
    engagement_id: EngagementId
    path: DocumentPath
    content_type: ContentType
    size_bytes: Annotated[int, Field(ge=0)]
    sha256: Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")]
    version: Annotated[int, Field(ge=1)]
    searchable: bool
    created_at: datetime
    updated_at: datetime
