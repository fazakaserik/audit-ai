"""Structured JSON logging via structlog."""

from __future__ import annotations

import logging
from uuid import UUID

import structlog


def configure_logging(*, json_logs: bool = True) -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_logs:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_context(
    *,
    request_id: UUID | str | None = None,
    upload_id: UUID | str | None = None,
    job_id: UUID | str | None = None,
    engagement_id: str | None = None,
) -> None:
    """Bind correlation ids. Never pass document content or secrets."""
    payload: dict[str, str] = {}
    if request_id is not None:
        payload["request_id"] = str(request_id)
    if upload_id is not None:
        payload["upload_id"] = str(upload_id)
    if job_id is not None:
        payload["job_id"] = str(job_id)
    if engagement_id is not None:
        payload["engagement_id"] = engagement_id
    if payload:
        structlog.contextvars.bind_contextvars(**payload)


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()
