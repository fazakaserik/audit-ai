"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from backend.api.middleware import RequestIdMiddleware
from backend.api.problem_handlers import register_exception_handlers
from backend.api.routers import engagements, health
from backend.bootstrap import build_container
from backend.config import Settings
from backend.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging(json_logs=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        cfg = settings if settings is not None else Settings()
        container = build_container(cfg)
        app.state.container = container
        yield
        await container.engine.dispose()

    app = FastAPI(title="Audit Assistant API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(engagements.router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    cfg = Settings()
    uvicorn.run("backend.api.main:app", host=cfg.api_host, port=cfg.api_port, reload=False)
