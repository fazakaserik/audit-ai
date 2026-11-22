"""Ask question route."""

from __future__ import annotations

import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from backend.api.contracts.v1.mapping import answer_to_response
from backend.api.contracts.v1.requests import AskRequest
from backend.api.contracts.v1.responses import AskResponse
from backend.api.dependencies import get_bound, get_container
from backend.application.ask_question import ask_question
from backend.bootstrap import Container, SessionBound
from domain.answer import Question
from domain.common import RequestId
from domain.engagement import EngagementId
from domain.session import SessionId

router = APIRouter(prefix="/api/v1/engagements", tags=["ask"])


@router.post("/{engagement_id}/ask", response_model=AskResponse)
async def post_ask(
    engagement_id: EngagementId,
    body: AskRequest,
    request: Request,
    bound: Annotated[SessionBound, Depends(get_bound)],
    container: Annotated[Container, Depends(get_container)],
) -> AskResponse:
    question = Question(
        text=body.question,
        folder_scope=body.folder_prefix,
        auditor_role=body.auditor_role,
        topic=body.topic,
    )
    session_id = SessionId(body.session_id) if body.session_id is not None else None
    result = await ask_question(
        bound,
        chat=container.chat_model,
        embedder=container.embedder,
        settings=container.settings,
        engagement_id=engagement_id,
        question=question,
        session_id=session_id,
    )
    rid = getattr(request.state, "request_id", None)
    request_id = RequestId(rid) if isinstance(rid, UUID) else RequestId(uuid.uuid4())
    return answer_to_response(
        result.answer,
        session_id=result.session_id,
        turn_id=result.turn_id,
        request_id=request_id,
    )