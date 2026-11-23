"""Session list and detail controllers."""

from __future__ import annotations

import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from backend.application.api.contracts.v1.mapping import (
    session_detail_to_response,
    session_to_summary,
    to_contract_page,
)
from backend.application.api.contracts.v1.page import Page
from backend.application.api.contracts.v1.responses import (
    SessionDetailResponse,
    SessionSummaryResponse,
)
from backend.application.api.dependencies import get_bound
from backend.application.wiring import SessionBound
from backend.domain.common import RequestId
from backend.domain.engagement import EngagementId
from backend.domain.session import SessionId

router = APIRouter(prefix="/api/v1/engagements", tags=["sessions"])


@router.get("/{engagement_id}/sessions", response_model=Page[SessionSummaryResponse])
async def get_sessions_list(
    engagement_id: EngagementId,
    bound: Annotated[SessionBound, Depends(get_bound)],
    limit: int = 50,
    offset: int = 0,
) -> Page[SessionSummaryResponse]:
    page = await bound.sessions.list_sessions(
        engagement_id=engagement_id,
        limit=limit,
        offset=offset,
    )
    return to_contract_page(page, session_to_summary)


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
    rid = getattr(request.state, "request_id", None)
    request_id = RequestId(rid) if isinstance(rid, UUID) else RequestId(uuid.uuid4())
    detail = await bound.sessions.get_session(
        engagement_id=engagement_id,
        session_id=SessionId(session_id),
    )
    return session_detail_to_response(detail, request_id=request_id)
