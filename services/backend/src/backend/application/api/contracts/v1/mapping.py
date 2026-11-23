"""Map domain entities to v1 contract responses."""

from __future__ import annotations

from typing import assert_never

from backend.application.api.contracts.v1.responses import (
    AnsweredResponse,
    AskResponse,
    CitationResponse,
    DocumentResponse,
    EngagementResponse,
    InsufficientEvidenceResponse,
    LlmUsageResponse,
    SessionDetailResponse,
    SessionSummaryResponse,
    SuggestedClientQuestionResponse,
    TurnResponse,
    UploadItemResponse,
    UploadResponse,
    UploadSummaryResponse,
)
from backend.domain.answer import Answer, Answered, AnswerStatus, Citation, InsufficientEvidence
from backend.domain.common import RequestId
from backend.domain.document import Document
from backend.domain.engagement import Engagement
from backend.domain.session import LlmUsage, Session, SessionId, Turn, TurnId
from backend.domain.upload import Upload, UploadItem


def usage_to_response(usage: LlmUsage) -> LlmUsageResponse:
    return LlmUsageResponse(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
    )


def citation_to_response(citation: Citation) -> CitationResponse:
    return CitationResponse(
        marker=citation.marker,
        chunk_id=citation.chunk_id,
        document_id=citation.document_id,
        document_path=citation.document_path,
        page=citation.page,
        heading_path=citation.heading_path,
        snippet=citation.snippet,
        score=citation.score,
    )


def answer_to_response(
    answer: Answer,
    *,
    session_id: SessionId,
    turn_id: TurnId,
    request_id: RequestId,
    usage: LlmUsage | None = None,
    session_total_tokens: int | None = None,
) -> AskResponse:
    usage_response = usage_to_response(usage or LlmUsage())
    total = (
        session_total_tokens if session_total_tokens is not None else usage_response.total_tokens
    )
    match answer:
        case Answered():
            return AnsweredResponse(
                status="answered",
                answer=answer.text,
                citations=tuple(citation_to_response(c) for c in answer.citations),
                session_id=session_id,
                turn_id=turn_id,
                request_id=request_id,
                usage=usage_response,
                session_total_tokens=total,
            )
        case InsufficientEvidence():
            return InsufficientEvidenceResponse(
                status="insufficient_evidence",
                reason=answer.reason,
                partial_citations=tuple(citation_to_response(c) for c in answer.partial_citations),
                uncertainties=answer.uncertainties,
                suggested_client_questions=tuple(
                    SuggestedClientQuestionResponse(
                        question=q.question,
                        rationale=q.rationale,
                    )
                    for q in answer.suggested_client_questions
                ),
                session_id=session_id,
                turn_id=turn_id,
                request_id=request_id,
                usage=usage_response,
                session_total_tokens=total,
            )
        case _ as unreachable:
            assert_never(unreachable)


def engagement_to_response(engagement: Engagement, *, document_count: int) -> EngagementResponse:
    return EngagementResponse(
        id=engagement.id,
        name=engagement.name,
        document_count=document_count,
        created_at=engagement.created_at,
        updated_at=engagement.updated_at,
    )


def document_to_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        path=document.path,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        searchable=document.searchable,
        version=document.version,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def upload_item_to_response(item: UploadItem) -> UploadItemResponse:
    return UploadItemResponse(
        id=item.id,
        document_path=item.document_path,
        status=item.status,
        reason=item.reason,
    )


def upload_to_summary(upload: Upload) -> UploadSummaryResponse:
    return UploadSummaryResponse(
        id=upload.id,
        engagement_id=upload.engagement_id,
        target_folder=upload.target_folder,
        status=upload.status,
        completed_at=upload.completed_at,
        created_at=upload.created_at,
        updated_at=upload.updated_at,
    )


def upload_to_response(upload: Upload, items: list[UploadItem]) -> UploadResponse:
    return UploadResponse(
        id=upload.id,
        engagement_id=upload.engagement_id,
        target_folder=upload.target_folder,
        status=upload.status,
        completed_at=upload.completed_at,
        items=tuple(upload_item_to_response(i) for i in items),
        created_at=upload.created_at,
        updated_at=upload.updated_at,
    )


def session_to_summary(session: Session) -> SessionSummaryResponse:
    return SessionSummaryResponse(
        id=session.id,
        engagement_id=session.engagement_id,
        title=session.title,
        turn_count=session.turn_count,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def turn_to_response(
    turn: Turn,
    *,
    request_id: RequestId,
    session_total_tokens: int | None = None,
) -> TurnResponse:
    usage = turn.usage or LlmUsage()
    total = session_total_tokens if session_total_tokens is not None else usage.total_tokens
    answer_response = answer_to_response(
        turn.answer,
        session_id=turn.session_id,
        turn_id=turn.id,
        request_id=request_id,
        usage=usage,
        session_total_tokens=total,
    )
    return TurnResponse(
        id=turn.id,
        ordinal=turn.ordinal,
        question=turn.question.text,
        folder_scope=turn.question.folder_scope,
        auditor_role=turn.question.auditor_role,
        topic=turn.question.topic,
        standalone_question=turn.standalone_question,
        answer=answer_response,
        created_at=turn.created_at,
        thinking_text=turn.thinking_text,
        thinking_seconds=turn.thinking_seconds,
    )


def session_to_detail(
    session: Session,
    turns: list[Turn],
    *,
    request_id: RequestId,
) -> SessionDetailResponse:
    summary = session_to_summary(session)
    running = 0
    turn_responses: list[TurnResponse] = []
    for turn in turns:
        running += turn.usage.total_tokens if turn.usage is not None else 0
        turn_responses.append(
            turn_to_response(turn, request_id=request_id, session_total_tokens=running)
        )
    return SessionDetailResponse(
        id=summary.id,
        engagement_id=summary.engagement_id,
        title=summary.title,
        turn_count=summary.turn_count,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        turns=tuple(turn_responses),
    )


def answer_status(answer: Answer) -> AnswerStatus:
    match answer:
        case Answered():
            return AnswerStatus.ANSWERED
        case InsufficientEvidence():
            return AnswerStatus.INSUFFICIENT_EVIDENCE
        case _ as unreachable:
            assert_never(unreachable)
