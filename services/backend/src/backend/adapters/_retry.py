"""Shared tenacity retry knobs for model/embedding adapters."""

from __future__ import annotations

from tenacity import wait_exponential_jitter

MAX_ATTEMPTS = 3
RETRY_WAIT = wait_exponential_jitter(initial=0.5, max=8.0)
