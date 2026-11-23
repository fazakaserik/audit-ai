"""Ask question controllers (sync + SSE stream)."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.application.api.contracts.v1.mapping import ask_result_to_response
from backend.application.api.contracts.v1.requests import AskRequest
from backend.application.api.contracts.v1.responses import AskResponse
from backend.application.api.dependencies import get_bound
from backend.application.api.problem_handlers import http_status_for
from backend.application.dto import AskStreamError, AskStreamFinal, AskStreamThinkingDone
from backend.application.wiring import SessionBound
from backend.domain.answer import Question
from backend.domain.common import RequestId
from backend.domain.engagement import EngagementId
from backend.domain.errors import DomainError, ErrorCode
from backend.domain.session import SessionId
from backend.logging import get_logger

router = APIRouter(prefix="/api/v1/engagements", tags=["ask"])
log = get_logger(__name__)

_PROGRESS_EVENT_TYPES = frozenset(
    {
        "stage",
        "sources",
        "thinking_delta",
        "thinking_done",
        "tool_call",
        "tool_result",
    }
)


def _question_from_body(body: AskRequest) -> tuple[Question, SessionId | None]:
    question = Question(
        text=body.question,
        folder_scope=body.folder_prefix,
        auditor_role=body.auditor_role,
        topic=body.topic,
    )
    session_id = SessionId(body.session_id) if body.session_id is not None else None
    return question, session_id


def _request_id(request: Request) -> RequestId:
    rid = getattr(request.state, "request_id", None)
    return RequestId(rid) if isinstance(rid, UUID) else RequestId(uuid.uuid4())


def _sse(data: dict[str, object]) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


def _progress_event_payload(event: AskStreamThinkingDone | dict[str, object]) -> dict[str, object]:
    if isinstance(event, AskStreamThinkingDone):
        return {
            "type": event.type,
            "duration_seconds": event.duration_seconds,
        }
    return event


@router.post(
    "/{engagement_id}/ask",
    response_model=AskResponse,
    summary="Ask a question",
)
async def post_ask(
    engagement_id: EngagementId,
    body: AskRequest,
    request: Request,
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> AskResponse:
    """Ask a grounded question (creates or continues a session)."""
    question, session_id = _question_from_body(body)
    result = await bound.ask.ask_question(
        engagement_id=engagement_id,
        question=question,
        session_id=session_id,
    )
    return ask_result_to_response(result, request_id=_request_id(request))


@router.post(
    "/{engagement_id}/ask/stream",
    summary="Ask a question (SSE progress)",
)
async def post_ask_stream(
    engagement_id: EngagementId,
    body: AskRequest,
    request: Request,
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> StreamingResponse:
    """Stream dimmed pipeline progress, optional thinking, then the final answer."""
    question, session_id = _question_from_body(body)
    request_id = _request_id(request)

    async def event_gen() -> AsyncIterator[str]:
        async for event in bound.ask.ask_question_stream(
            engagement_id=engagement_id,
            question=question,
            session_id=session_id,
        ):
            if isinstance(event, AskStreamFinal):
                response = ask_result_to_response(event.result, request_id=request_id)
                yield _sse(
                    {
                        "type": "final",
                        "response": response.model_dump(mode="json"),
                    }
                )
            elif isinstance(event, AskStreamError):
                exc = event.error
                if isinstance(exc, DomainError):
                    yield _sse(
                        {
                            "type": "error",
                            "status": http_status_for(exc.code),
                            "code": exc.code.value,
                            "detail": exc.message,
                        }
                    )
                else:
                    log.exception("ask_stream_unhandled_error", error=str(exc))
                    yield _sse(
                        {
                            "type": "error",
                            "status": 500,
                            "code": ErrorCode.INTERNAL_ERROR.value,
                            "detail": "An unexpected error occurred",
                        }
                    )
            elif isinstance(event, AskStreamThinkingDone):
                yield _sse(_progress_event_payload(event))
            else:
                payload = _progress_event_payload(event)
                event_type = payload.get("type")
                if event_type in _PROGRESS_EVENT_TYPES:
                    yield _sse(payload)
                elif event_type is not None:
                    yield _sse(
                        {
                            "type": "error",
                            "status": 500,
                            "code": "internal_error",
                            "detail": "unknown event",
                        }
                    )

    return StreamingResponse(event_gen(), media_type="text/event-stream")
