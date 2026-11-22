"""v1 request DTOs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from domain.document import FolderPath
from domain.engagement import EngagementId


class CreateEngagementRequest(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    id: EngagementId
    name: Annotated[str, Field(min_length=1, max_length=200)]


class AskRequest(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    question: Annotated[str, Field(min_length=1, max_length=2000)]
    session_id: UUID | None = None
    folder_prefix: FolderPath | None = None
    auditor_role: Annotated[str, Field(max_length=200)] | None = None
    topic: Annotated[str, Field(max_length=200)] | None = None

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped
