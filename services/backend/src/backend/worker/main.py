"""Ingestion worker entrypoint (claim loop)."""

from __future__ import annotations

import asyncio
import signal
import uuid

from backend.bootstrap import build_container
from backend.config import Settings
from backend.logging import bind_context, clear_context, configure_logging, get_logger

log = get_logger(__name__)


async def _run_loop(settings: Settings) -> None:
    container = build_container(settings)
    worker_id = f"worker-{uuid.uuid4()}"
    stop = asyncio.Event()

    def _stop(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            # Windows
            signal.signal(sig, lambda *_a: stop.set())

    log.info("worker_started", worker_id=worker_id)
    try:
        while not stop.is_set():
            async with container.session_factory() as session:
                bound = container.bind(session)
                item = await bound.jobs.claim_next(worker_id)
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
                # Full process_item pipeline lands in US3 tasks; acknowledge for now.
                await bound.jobs.complete(item.id, status="skipped", reason="processor_not_implemented")
                await session.commit()
    finally:
        await container.engine.dispose()
        log.info("worker_stopped", worker_id=worker_id)


def run() -> None:
    configure_logging(json_logs=True)
    settings = Settings()
    asyncio.run(_run_loop(settings))


if __name__ == "__main__":
    run()
