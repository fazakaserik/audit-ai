"""Session list and detail routes."""

from __future__ import annotations

import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from backend.api.contracts.v1.mapping import session_to_detail, session_to_summary
from backend.api.contracts.v1.page import Page
from backend.api.contracts.v1.responses import SessionDetailResponse, SessionSummaryResponse
from backend.api.dependencies import get_bound
from backend.application.get_session import get_session
from backend.application.list_sessions import list_sessions
from backend.bootstrap import SessionBound
from domain.common import RequestId
from domain.engagement import EngagementId
from domain.session import SessionId

router = APIRouter(prefix="/api/v1/engagements", tags=["sessions"])


@router.get("/{engagement_id}/sessions", response_model=Page[SessionSummaryResponse])
async def get_sessions_list(
    engagement_id: EngagementId,
    bound: Annotated[SessionBound, Depends(get_bound)],
    limit: int = 50,
    offset: int = 0,
) -> Page[SessionSummaryResponse]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    result = await list_sessions(
        bound.engagements,
        bound.sessions,
        engagement_id=engagement_id,
        limit=limit,
        offset=offset,
    )
    summaries = tuple(session_to_summary(session) for session in result.items)
    return Page(items=summaries, total=result.total, limit=limit, offset=offset)


@router.get(
    "/{engagement_id}/sessions/{session_id}",
    response_model=SessionDetailResponse,
)
async def get_session_detail(
    engagement_id: EngagementId,
    session_id: UUID,
    request: Request,
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> SessionDetailResponse:
    result = await get_session(
        bound.engagements,
        bound.sessions,
        engagement_id=engagement_id,
        session_id=SessionId(session_id),
    )
    rid = getattr(request.state, "request_id", None)
    request_id = RequestId(rid) if isinstance(rid, UUID) else RequestId(uuid.uuid4())
    return session_to_detail(
        result.session,
        list(result.turns),
        request_id=request_id,
    )