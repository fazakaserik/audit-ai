"""Question, citation, and answer union."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from domain.common import MODEL_CONFIG
from domain.document import DocumentId, DocumentPath, FolderPath
from domain.chunk import ChunkId


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class InsufficientReason(StrEnum):
    NO_RELEVANT_CHUNKS = "no_relevant_chunks"
    MODEL_JUDGED_INSUFFICIENT = "model_judged_insufficient"


class Question(BaseModel):
    model_config = MODEL_CONFIG

    text: Annotated[str, Field(min_length=1, max_length=2000)]
    folder_scope: FolderPath | None = None
    auditor_role: Annotated[str, Field(max_length=200)] | None = None
    topic: Annotated[str, Field(max_length=200)] | None = None

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question text must not be blank")
        return stripped


class Citation(BaseModel):
    model_config = MODEL_CONFIG

    marker: Annotated[int, Field(ge=1)]
    chunk_id: ChunkId
    document_id: DocumentId
    document_path: DocumentPath
    page: Annotated[int, Field(ge=1)] | None = None
    heading_path: tuple[str, ...] = ()
    snippet: Annotated[str, Field(min_length=1, max_length=500)]
    score: Annotated[float, Field(ge=0.0, le=1.0)]


class SuggestedClientQuestion(BaseModel):
    model_config = MODEL_CONFIG

    question: Annotated[str, Field(min_length=1, max_length=500)]
    rationale: Annotated[str, Field(min_length=1, max_length=500)]


class Answered(BaseModel):
    model_config = MODEL_CONFIG

    status: Literal[AnswerStatus.ANSWERED] = AnswerStatus.ANSWERED
    text: Annotated[str, Field(min_length=1)]
    citations: Annotated[tuple[Citation, ...], Field(min_length=1)]


class InsufficientEvidence(BaseModel):
    model_config = MODEL_CONFIG

    status: Literal[AnswerStatus.INSUFFICIENT_EVIDENCE] = AnswerStatus.INSUFFICIENT_EVIDENCE
    reason: InsufficientReason
    partial_citations: tuple[Citation, ...] = ()
    suggested_client_questions: Annotated[
        tuple[SuggestedClientQuestion, ...],
        Field(min_length=1, max_length=3),
    ]


Answer = Answered | InsufficientEvidence
