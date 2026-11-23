"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.applications import Starlette

from backend.application.wiring import SessionBound
from backend.bootstrap import Container


def get_container(request: Request) -> Container:
    state = cast(Starlette, request.app).state
    container_obj = getattr(state, "container", None)
    container = container_obj if isinstance(container_obj, Container) else None
    if container is None:
        msg = "application container is not configured"
        raise RuntimeError(msg)
    return container


async def get_session(
    container: Annotated[Container, Depends(get_container)],
) -> AsyncIterator[AsyncSession]:
    async with container.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_bound(
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
) -> SessionBound:
    return container.bind(session)
