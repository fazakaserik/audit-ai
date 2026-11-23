"""Ingestion worker claim loop (standalone or in-process with the API)."""

from __future__ import annotations

import asyncio
import signal
import uuid

from backend.application.rag.worker.process_item import process_upload_item
from backend.bootstrap import Container, build_container
from backend.config import Settings
from backend.logging import bind_context, clear_context, configure_logging, get_logger

log = get_logger(__name__)


async def run_worker_loop(
    container: Container,
    *,
    stop: asyncio.Event,
    worker_id: str | None = None,
) -> None:
    """Claim and process upload items until ``stop`` is set."""
    wid = worker_id or f"worker-{uuid.uuid4()}"
    log.info("worker_started", worker_id=wid)
    try:
        while not stop.is_set():
            async with container.session_factory() as session:
                bound = container.bind(session)
                item = await bound.jobs.claim_next(wid)
                if item is None:
                    await session.commit()
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=1.0)
                    except TimeoutError:
                        continue
                    break
                clear_context()
                bind_context(job_id=item.id, upload_id=item.upload_id)
                log.info("job_claimed", item_id=str(item.id), path=item.document_path)
                upload = await bound.uploads.get_by_id(item.upload_id)
                if upload is None:
                    await bound.jobs.complete(
                        item.id,
                        status="failed",
                        reason="upload record missing",
                    )
                    await session.commit()
                    continue

                await bound.uploads.mark_processing(item.upload_id)
                try:
                    outcome = await process_upload_item(
                        item=item,
                        engagement_id=upload.engagement_id,
                        documents=bound.documents,
                        storage=container.document_storage,
                        vector_index=bound.vector_index,
                        embedder=container.embedder,
                        uploads=bound.uploads,
                        document_parser=container.document_parser,
                        document_chunker=container.document_chunker,
                    )
                    await bound.jobs.complete(
                        item.id,
                        status=outcome.status.value,
                        reason=outcome.reason,
                    )
                    # Refresh after complete so terminal item status is visible.
                    upload_status = await bound.uploads.refresh_status(item.upload_id)
                    log.info(
                        "job_completed",
                        item_id=str(item.id),
                        path=item.document_path,
                        status=outcome.status.value,
                        reason=outcome.reason,
                        upload_status=upload_status.status.value,
                    )
                except Exception as exc:
                    log.exception("job_failed", item_id=str(item.id), path=item.document_path)
                    await bound.jobs.fail_for_retry(item.id, reason=str(exc))
                    await bound.uploads.refresh_status(item.upload_id)
                await session.commit()
    finally:
        log.info("worker_stopped", worker_id=wid)


async def _run_standalone(settings: Settings) -> None:
    container = build_container(settings)
    stop = asyncio.Event()

    def _stop(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_a: stop.set())

    try:
        await run_worker_loop(container, stop=stop)
    finally:
        await container.engine.dispose()


def run() -> None:
    settings = Settings()
    configure_logging(json_logs=settings.log_json, level=settings.log_level)
    asyncio.run(_run_standalone(settings))


if __name__ == "__main__":
    run()
