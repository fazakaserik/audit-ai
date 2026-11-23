"""Shared ORM row ↔ domain model helpers for Postgres repositories."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import assert_never
from uuid import UUID, uuid4

from backend.domain.answer import (
    Answer,
    Answered,
    AnswerStatus,
    Citation,
    InsufficientEvidence,
    InsufficientReason,
    Question,
    SuggestedClientQuestion,
)
from backend.domain.chunk import ChunkId
from backend.domain.document import ContentType, Document, DocumentId
from backend.domain.engagement import Engagement
from backend.domain.session import LlmUsage, Session, SessionId, Turn, TurnId
from backend.domain.upload import (
    Upload,
    UploadId,
    UploadItem,
    UploadItemId,
    UploadItemStatus,
    UploadStatus,
)
from backend.infrastructure.postgres.models import (
    DocumentRow,
    EngagementRow,
    SessionRow,
    SessionTurnRow,
    TurnCitationRow,
    TurnSuggestedQuestionRow,
    UploadItemRow,
    UploadRow,
)


def aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def engagement_from_row(row: EngagementRow) -> Engagement:
    return Engagement(
        id=row.id,
        name=row.name,
        created_at=aware(row.created_at),
        updated_at=aware(row.updated_at),
    )


def document_from_row(row: DocumentRow) -> Document:
    return Document(
        id=DocumentId(row.id),
        engagement_id=row.engagement_id,
        path=row.path,
        content_type=ContentType(row.content_type),
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        version=row.version,
        searchable=row.searchable,
        created_at=aware(row.created_at),
        updated_at=aware(row.updated_at),
    )


def session_from_row(row: SessionRow) -> Session:
    return Session(
        id=SessionId(row.id),
        engagement_id=row.engagement_id,
        title=row.title,
        turn_count=row.turn_count,
        created_at=aware(row.created_at),
        updated_at=aware(row.updated_at),
    )


def citation_from_row(row: TurnCitationRow) -> Citation:
    return Citation(
        marker=row.marker,
        chunk_id=ChunkId(row.chunk_id),
        document_id=DocumentId(row.document_id),
        document_path=row.document_path,
        page=row.page,
        heading_path=tuple(row.heading_path or ()),
        snippet=row.snippet,
        score=row.score,
    )


def citation_row(
    *,
    turn_id: UUID,
    kind: str,
    citation: Citation,
) -> TurnCitationRow:
    return TurnCitationRow(
        id=uuid4(),
        turn_id=turn_id,
        kind=kind,
        marker=citation.marker,
        chunk_id=citation.chunk_id,
        document_id=citation.document_id,
        document_path=citation.document_path,
        page=citation.page,
        heading_path=list(citation.heading_path),
        snippet=citation.snippet,
        score=citation.score,
    )


def answer_from_turn_row(row: SessionTurnRow) -> Answer:
    status = row.answer_status
    if status == AnswerStatus.ANSWERED:
        citations = tuple(
            citation_from_row(item)
            for item in sorted(row.citations, key=lambda c: c.marker)
            if item.kind == "answer"
        )
        text = row.answer_text or ""
        return Answered(text=text, citations=citations)
    if status == AnswerStatus.INSUFFICIENT_EVIDENCE:
        partial = tuple(
            citation_from_row(item)
            for item in sorted(row.citations, key=lambda c: c.marker)
            if item.kind == "partial"
        )
        suggestions = tuple(
            SuggestedClientQuestion(question=item.question, rationale=item.rationale)
            for item in sorted(row.suggested_questions, key=lambda s: s.ordinal)
        )
        reason_raw = row.insufficient_reason or InsufficientReason.MODEL_JUDGED_INSUFFICIENT.value
        if reason_raw == "no_relevant_passages":
            reason_raw = InsufficientReason.NO_RELEVANT_CHUNKS.value
        return InsufficientEvidence(
            reason=InsufficientReason(reason_raw),
            partial_citations=partial,
            suggested_client_questions=suggestions,
        )
    msg = f"unknown answer status: {status}"
    raise ValueError(msg)


def upload_from_row(row: UploadRow) -> Upload:
    return Upload(
        id=UploadId(row.id),
        engagement_id=row.engagement_id,
        target_folder=row.target_folder,
        status=UploadStatus(row.status),
        completed_at=aware(row.completed_at) if row.completed_at is not None else None,
        created_at=aware(row.created_at),
        updated_at=aware(row.updated_at),
    )


def upload_item_from_row(row: UploadItemRow) -> UploadItem:
    return UploadItem(
        id=UploadItemId(row.id),
        upload_id=UploadId(row.upload_id),
        document_path=row.document_path,
        status=UploadItemStatus(row.status),
        reason=row.reason,
        attempts=row.attempts,
        processing_started_at=(
            aware(row.processing_started_at) if row.processing_started_at is not None else None
        ),
        processing_finished_at=(
            aware(row.processing_finished_at) if row.processing_finished_at is not None else None
        ),
        embedding_prompt_tokens=row.embedding_prompt_tokens,
        embedding_total_tokens=row.embedding_total_tokens,
        chunk_count=row.chunk_count,
        chunk_token_sum=row.chunk_token_sum,
        created_at=aware(row.created_at),
        updated_at=aware(row.updated_at),
    )


def usage_from_turn_row(row: SessionTurnRow) -> LlmUsage | None:
    if (
        row.usage_prompt_tokens is None
        and row.usage_completion_tokens is None
        and row.usage_total_tokens is None
    ):
        return None
    return LlmUsage(
        prompt_tokens=row.usage_prompt_tokens or 0,
        completion_tokens=row.usage_completion_tokens or 0,
        total_tokens=row.usage_total_tokens or 0,
    )


def turn_from_row(row: SessionTurnRow) -> Turn:
    return Turn(
        id=TurnId(row.id),
        session_id=SessionId(row.session_id),
        ordinal=row.ordinal,
        question=Question(
            text=row.question_text,
            folder_scope=row.question_folder_scope,
            auditor_role=row.question_auditor_role,
            topic=row.question_topic,
        ),
        standalone_question=row.standalone_question,
        answer=answer_from_turn_row(row),
        created_at=aware(row.created_at),
        thinking_text=row.thinking_text,
        thinking_seconds=row.thinking_seconds,
        usage=usage_from_turn_row(row),
    )


def populate_answer_rows(row: SessionTurnRow, answer: Answer) -> None:
    match answer:
        case Answered():
            row.answer_status = AnswerStatus.ANSWERED.value
            row.answer_text = answer.text
            row.insufficient_reason = None
            row.citations = [
                citation_row(turn_id=row.id, kind="answer", citation=citation)
                for citation in answer.citations
            ]
            row.suggested_questions = []
        case InsufficientEvidence():
            row.answer_status = AnswerStatus.INSUFFICIENT_EVIDENCE.value
            row.answer_text = None
            row.insufficient_reason = answer.reason.value
            row.citations = [
                citation_row(turn_id=row.id, kind="partial", citation=citation)
                for citation in answer.partial_citations
            ]
            row.suggested_questions = [
                TurnSuggestedQuestionRow(
                    id=uuid4(),
                    turn_id=row.id,
                    ordinal=index,
                    question=item.question,
                    rationale=item.rationale,
                )
                for index, item in enumerate(answer.suggested_client_questions)
            ]
        case _:
            assert_never(answer)
