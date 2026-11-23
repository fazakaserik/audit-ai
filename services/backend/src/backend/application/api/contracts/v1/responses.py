"""v1 response DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel

from backend.domain.answer import InsufficientReason
from backend.domain.common import RequestId
from backend.domain.document import ContentType
from backend.domain.engagement import EngagementId
from backend.domain.upload import UploadItemStatus, UploadStatus

_CFG = ConfigDict(frozen=True, strict=True, extra="forbid")


class EngagementResponse(BaseModel):
    model_config = _CFG

    id: EngagementId
    name: str
    document_count: Annotated[int, Field(ge=0)]
    created_at: datetime
    updated_at: datetime


class DocumentResponse(BaseModel):
    model_config = _CFG

    id: UUID
    path: str
    content_type: ContentType
    size_bytes: Annotated[int, Field(ge=0)]
    searchable: bool
    version: Annotated[int, Field(ge=1)]
    created_at: datetime
    updated_at: datetime


class DocumentListingResponse(BaseModel):
    model_config = _CFG

    items: tuple[DocumentResponse, ...]
    folders: tuple[str, ...]
    total: Annotated[int, Field(ge=0)]
    limit: Annotated[int, Field(ge=1, le=200)]
    offset: Annotated[int, Field(ge=0)]


class UploadAcceptedResponse(BaseModel):
    model_config = _CFG

    upload_id: UUID
    status: Literal[UploadStatus.QUEUED] = UploadStatus.QUEUED
    request_id: RequestId


class UploadItemResponse(BaseModel):
    model_config = _CFG

    id: UUID
    document_path: str
    status: UploadItemStatus
    reason: str | None = None


class UploadSummaryResponse(BaseModel):
    model_config = _CFG

    id: UUID
    engagement_id: EngagementId
    target_folder: str
    status: UploadStatus
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UploadResponse(BaseModel):
    model_config = _CFG

    id: UUID
    engagement_id: EngagementId
    target_folder: str
    status: UploadStatus
    completed_at: datetime | None
    items: tuple[UploadItemResponse, ...]
    created_at: datetime
    updated_at: datetime


class CitationResponse(BaseModel):
    model_config = _CFG

    marker: Annotated[int, Field(ge=1)]
    chunk_id: UUID
    document_id: UUID
    document_path: str
    page: Annotated[int, Field(ge=1)] | None = None
    heading_path: tuple[str, ...] = ()
    snippet: str
    score: Annotated[float, Field(ge=0.0, le=1.0)]


class SuggestedClientQuestionResponse(BaseModel):
    model_config = _CFG

    question: str
    rationale: str


class LlmUsageResponse(BaseModel):
    model_config = _CFG

    prompt_tokens: Annotated[int, Field(ge=0)]
    completion_tokens: Annotated[int, Field(ge=0)]
    total_tokens: Annotated[int, Field(ge=0)]


class AnsweredResponse(BaseModel):
    model_config = _CFG

    status: Literal["answered"] = "answered"
    answer: str
    citations: Annotated[tuple[CitationResponse, ...], Field(min_length=1)]
    session_id: UUID
    turn_id: UUID
    request_id: RequestId
    usage: LlmUsageResponse
    session_total_tokens: Annotated[int, Field(ge=0)]


class InsufficientEvidenceResponse(BaseModel):
    model_config = _CFG

    status: Literal["insufficient_evidence"] = "insufficient_evidence"
    reason: InsufficientReason
    partial_citations: tuple[CitationResponse, ...] = ()
    uncertainties: Annotated[tuple[str, ...], Field(max_length=5)] = ()
    suggested_client_questions: Annotated[
        tuple[SuggestedClientQuestionResponse, ...],
        Field(min_length=1, max_length=3),
    ]
    session_id: UUID
    turn_id: UUID
    request_id: RequestId
    usage: LlmUsageResponse
    session_total_tokens: Annotated[int, Field(ge=0)]


AskResponse = AnsweredResponse | InsufficientEvidenceResponse


class AskResponseRoot(RootModel[AskResponse]):
    root: AskResponse


class SessionSummaryResponse(BaseModel):
    model_config = _CFG

    id: UUID
    engagement_id: EngagementId
    title: str
    turn_count: Annotated[int, Field(ge=0)]
    created_at: datetime
    updated_at: datetime


class TurnResponse(BaseModel):
    model_config = _CFG

    id: UUID
    ordinal: Annotated[int, Field(ge=0)]
    question: str
    folder_scope: str | None
    auditor_role: str | None
    topic: str | None
    standalone_question: str
    answer: AskResponse
    created_at: datetime
    thinking_text: str | None = None
    thinking_seconds: float | None = None


class SessionDetailResponse(SessionSummaryResponse):
    turns: tuple[TurnResponse, ...]


class HealthLiveResponse(BaseModel):
    model_config = _CFG

    status: Literal["ok"] = "ok"


class DependencyCheck(BaseModel):
    model_config = _CFG

    ok: bool
    detail: str | None = None


class HealthReadyResponse(BaseModel):
    model_config = _CFG

    status: Literal["ready", "not_ready"]
    checks: dict[str, DependencyCheck]
