"""Backward-compatible re-export; prefer ``backend.infrastructure.llm.retry``."""

from backend.infrastructure.llm.retry import MAX_ATTEMPTS, RETRY_WAIT

__all__ = ["MAX_ATTEMPTS", "RETRY_WAIT"]
