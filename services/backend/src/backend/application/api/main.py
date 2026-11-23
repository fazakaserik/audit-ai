"""FastAPI application factory."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.application.api.middleware import RequestIdMiddleware
from backend.application.api.problem_handlers import register_exception_handlers
from backend.application.api.routers import ask, documents, engagements, health, sessions, uploads
from backend.application.rag.worker.main import run_worker_loop
from backend.bootstrap import Container, build_container
from backend.config import Settings
from backend.infrastructure.postgres.migrate import upgrade_head
from backend.logging import configure_logging, get_logger

log = get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    container: Container | None = None,
    run_worker: bool | None = None,
) -> FastAPI:
    cfg = settings if settings is not None else Settings()
    configure_logging(json_logs=cfg.log_json, level=cfg.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = container is None
        if owned:
            # Alembic's env uses asyncio.run; run off the request loop.
            log.info("database_migrate_start")
            await asyncio.to_thread(upgrade_head, cfg.database_url)
            # Belt-and-suspenders if a migration path still touches logging.
            configure_logging(json_logs=cfg.log_json, level=cfg.log_level)
            log.info("database_migrate_complete")
        active = container if container is not None else build_container(cfg)
        app.state.container = active

        if run_worker is None:
            # Injected containers are for tests; don't start a claim loop by default.
            worker_enabled = False if container is not None else cfg.run_worker_in_api
        else:
            worker_enabled = run_worker
        stop = asyncio.Event()
        worker_task: asyncio.Task[None] | None = None
        if worker_enabled:
            log.info("worker_enabled", run_in_api=True)
            worker_task = asyncio.create_task(
                run_worker_loop(active, stop=stop),
                name="upload-worker",
            )

        try:
            yield
        finally:
            stop.set()
            if worker_task is not None:
                await worker_task
            if owned:
                await active.engine.dispose()

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
