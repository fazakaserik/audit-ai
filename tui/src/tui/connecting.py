"""API connectivity helpers used before the main screen stack."""

from __future__ import annotations

import time
from collections.abc import Callable

from cli.client import AuditApiClient, CliApiError

CONNECT_BACKOFF_SECONDS = (1, 2, 3, 5, 10)


def wait_for_api(
    client: AuditApiClient,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Retry `/health/live` with backoff. Return True on success, False if unreachable."""
    for attempt, delay in enumerate((0, *CONNECT_BACKOFF_SECONDS)):
        if delay:
            sleep(delay)
        try:
            client.check_live()
        except CliApiError:
            if attempt == len(CONNECT_BACKOFF_SECONDS):
                break
            continue
        return True
    return False
