"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.application.api.controllers import (
    ask,
    documents,
    engagements,
    health,
    sessions,
    uploads,
)
from backend.application.api.middleware import RequestIdMiddleware
from backend.application.api.problem_handlers import register_exception_handlers
from backend.bootstrap import Container, build_container
from backend.config import Settings
from backend.logging import configure_logging, get_logger

log = get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    container: Container | None = None,
) -> FastAPI:
    cfg = settings if settings is not None else Settings()
    configure_logging(json_logs=cfg.log_json, level=cfg.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        owned = container is None
        active = container if container is not None else build_container(cfg)
        app.state.container = active
        log.info("api_started")
        try:
            yield
        finally:
            if owned:
                await active.engine.dispose()
            log.info("api_stopped")

    docs_url = "/docs" if cfg.enable_api_docs else None
    redoc_url = "/redoc" if cfg.enable_api_docs else None
    openapi_url = "/openapi.json" if cfg.enable_api_docs else None
    app = FastAPI(
        title="AIditor API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    if container is not None:
        # Available before lifespan for ASGITransport tests that skip lifespan.
        app.state.container = container
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(engagements.router)
    app.include_router(documents.router)
    app.include_router(uploads.router)
    app.include_router(ask.router)
    app.include_router(sessions.router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    cfg = Settings()
    uvicorn.run(
        "backend.application.api.main:app", host=cfg.api_host, port=cfg.api_port, reload=False
    )
