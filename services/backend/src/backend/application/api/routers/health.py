"""Health endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text

from backend.application.api.contracts.v1.responses import (
    DependencyCheck,
    HealthLiveResponse,
    HealthReadyResponse,
)
from backend.application.api.dependencies import get_container
from backend.bootstrap import Container

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthLiveResponse)
async def live() -> HealthLiveResponse:
    return HealthLiveResponse()


@router.get("/health/ready", response_model=HealthReadyResponse)
async def ready(
    container: Annotated[Container, Depends(get_container)],
    response: Response,
) -> HealthReadyResponse:
    checks: dict[str, DependencyCheck] = {}

    try:
        async with container.session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = DependencyCheck(ok=True)
    except Exception as exc:
        checks["postgres"] = DependencyCheck(ok=False, detail=type(exc).__name__)

    try:
        embedded = await container.embedder.embed(["health-check"])
        if not embedded.vectors or not embedded.vectors[0]:
            checks["embeddings"] = DependencyCheck(ok=False, detail="empty_embedding")
        else:
            checks["embeddings"] = DependencyCheck(ok=True)
    except Exception as exc:
        checks["embeddings"] = DependencyCheck(ok=False, detail=type(exc).__name__)

    ready_ok = all(c.ok for c in checks.values())
    if not ready_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthReadyResponse(
        status="ready" if ready_ok else "not_ready",
        checks=checks,
    )
