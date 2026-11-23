"""Engagement controllers."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from backend.application.api.contracts.v1.mapping import (
    engagement_view_to_response,
    to_contract_page,
)
from backend.application.api.contracts.v1.page import Page
from backend.application.api.contracts.v1.requests import (
    CreateEngagementRequest,
    UpdateEngagementRequest,
)
from backend.application.api.contracts.v1.responses import EngagementResponse
from backend.application.api.dependencies import get_bound
from backend.application.wiring import SessionBound
from backend.domain.engagement import EngagementId

router = APIRouter(prefix="/api/v1/engagements", tags=["engagements"])


@router.post("", response_model=EngagementResponse, status_code=status.HTTP_201_CREATED)
async def post_engagement(
    body: CreateEngagementRequest,
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> EngagementResponse:
    view = await bound.engagements.create(
        engagement_id=body.id,
        name=body.name,
    )
    return engagement_view_to_response(view)


@router.get("", response_model=Page[EngagementResponse])
async def list_engagements(
    bound: Annotated[SessionBound, Depends(get_bound)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EngagementResponse]:
    page = await bound.engagements.list(limit=limit, offset=offset)
    return to_contract_page(page, engagement_view_to_response)


@router.get("/{engagement_id}", response_model=EngagementResponse)
async def get_engagement(
    engagement_id: EngagementId,
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> EngagementResponse:
    view = await bound.engagements.get(engagement_id=engagement_id)
    return engagement_view_to_response(view)


@router.patch("/{engagement_id}", response_model=EngagementResponse)
async def patch_engagement(
    engagement_id: EngagementId,
    body: UpdateEngagementRequest,
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> EngagementResponse:
    view = await bound.engagements.rename(
        engagement_id=engagement_id,
        name=body.name,
    )
    return engagement_view_to_response(view)


@router.delete("/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_engagement(
    engagement_id: EngagementId,
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> Response:
    await bound.engagements.delete(engagement_id=engagement_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
