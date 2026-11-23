"""Engagement controllers."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.application.api.contracts.v1.page import Page
from backend.application.api.contracts.v1.requests import CreateEngagementRequest
from backend.application.api.contracts.v1.responses import EngagementResponse
from backend.application.api.dependencies import get_bound
from backend.bootstrap import SessionBound
from backend.domain.engagement import EngagementId

router = APIRouter(prefix="/api/v1/engagements", tags=["engagements"])


@router.post("", response_model=EngagementResponse, status_code=status.HTTP_201_CREATED)
async def post_engagement(
    body: CreateEngagementRequest,
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> EngagementResponse:
    return await bound.engagements.create(
        engagement_id=body.id,
        name=body.name,
    )


@router.get("", response_model=Page[EngagementResponse])
async def list_engagements(
    bound: Annotated[SessionBound, Depends(get_bound)],
    limit: int = 50,
    offset: int = 0,
) -> Page[EngagementResponse]:
    return await bound.engagements.list(limit=limit, offset=offset)


@router.get("/{engagement_id}", response_model=EngagementResponse)
async def get_engagement(
    engagement_id: EngagementId,
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> EngagementResponse:
    return await bound.engagements.get(engagement_id=engagement_id)
