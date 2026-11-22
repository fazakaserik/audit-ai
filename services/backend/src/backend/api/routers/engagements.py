"""Engagement routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.contracts.v1.mapping import engagement_to_response
from backend.api.contracts.v1.page import Page
from backend.api.contracts.v1.requests import CreateEngagementRequest
from backend.api.contracts.v1.responses import EngagementResponse
from backend.api.dependencies import get_bound
from backend.application.create_engagement import create_engagement
from backend.bootstrap import SessionBound
from domain.engagement import EngagementId
from domain.errors import NotFoundError

router = APIRouter(prefix="/api/v1/engagements", tags=["engagements"])


@router.post("", response_model=EngagementResponse, status_code=status.HTTP_201_CREATED)
async def post_engagement(
    body: CreateEngagementRequest,
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> EngagementResponse:
    created = await create_engagement(
        bound.engagements,
        engagement_id=body.id,
        name=body.name,
    )
    return engagement_to_response(created, document_count=0)


@router.get("", response_model=Page[EngagementResponse])
async def list_engagements(
    bound: Annotated[SessionBound, Depends(get_bound)],
    limit: int = 50,
    offset: int = 0,
) -> Page[EngagementResponse]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    items, total = await bound.engagements.list(limit=limit, offset=offset)
    responses: list[EngagementResponse] = []
    for eng in items:
        count = await bound.engagements.count_documents(eng.id)
        responses.append(engagement_to_response(eng, document_count=count))
    return Page(items=tuple(responses), total=total, limit=limit, offset=offset)


@router.get("/{engagement_id}", response_model=EngagementResponse)
async def get_engagement(
    engagement_id: EngagementId,
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> EngagementResponse:
    eng = await bound.engagements.get(engagement_id)
    if eng is None:
        raise NotFoundError(f"engagement not found: {engagement_id}")
    count = await bound.engagements.count_documents(eng.id)
    return engagement_to_response(eng, document_count=count)
