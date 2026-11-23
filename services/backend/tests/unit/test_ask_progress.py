"""Unit tests for CollectingAskProgress."""

from __future__ import annotations

from backend.application.rag.progress import CollectingAskProgress, SourceHit


async def test_collecting_progress_emits_and_accumulates() -> None:
    emitted: list[dict[str, object]] = []

    async def emit(event: dict[str, object]) -> None:
        emitted.append(event)

    progress = CollectingAskProgress()
    progress.bind_emitter(emit)
    await progress.stage("retrieve")
    await progress.sources([SourceHit(path="policies/a.md", score=0.9)])
    callbacks = progress.thinking_callbacks()
    await callbacks.on_delta("step 1 ")
    await callbacks.on_delta("step 2")
    callbacks.on_seconds(2.5)
    callbacks.on_seconds(0.5)

    assert progress.stages == ["retrieve"]
    assert progress.thinking_seconds == 3.0
    assert "".join(progress.thinking_chunks) == "step 1 step 2"
    assert emitted[0]["type"] == "stage"
    assert emitted[1]["type"] == "sources"
    assert emitted[2]["type"] == "thinking_delta"
