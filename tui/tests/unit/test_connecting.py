"""Tests for TUI API connection retry."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from backend.domain.errors import ErrorCode
from cli.client import AuditApiClient, CliApiError
from tui.connecting import CONNECT_BACKOFF_SECONDS, wait_for_api


def test_check_live_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health/live"
        return httpx.Response(200, json={"status": "ok"}, request=request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://test")
    client = AuditApiClient(http_client=http_client)
    client.check_live()


def test_wait_for_api_retries_then_succeeds() -> None:
    client = MagicMock(spec=AuditApiClient)
    client.base_url = "http://localhost:8000"
    client.check_live.side_effect = [
        CliApiError(code=ErrorCode.DEPENDENCY_UNAVAILABLE, detail="down", status=0),
        CliApiError(code=ErrorCode.DEPENDENCY_UNAVAILABLE, detail="down", status=0),
        None,
    ]
    sleeps: list[float] = []

    assert wait_for_api(client, sleep=sleeps.append) is True
    assert client.check_live.call_count == 3
    assert sleeps == [1, 2]


def test_wait_for_api_gives_up_after_backoff() -> None:
    client = MagicMock(spec=AuditApiClient)
    client.base_url = "http://localhost:8000"
    client.check_live.side_effect = CliApiError(
        code=ErrorCode.DEPENDENCY_UNAVAILABLE,
        detail="down",
        status=0,
    )
    sleeps: list[float] = []

    assert wait_for_api(client, sleep=sleeps.append) is False
    assert client.check_live.call_count == len(CONNECT_BACKOFF_SECONDS) + 1
    assert sleeps == list(CONNECT_BACKOFF_SECONDS)


def test_check_live_maps_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://test")
    client = AuditApiClient(base_url="http://test", http_client=http_client)

    with pytest.raises(CliApiError) as exc_info:
        client.check_live()

    err = exc_info.value
    assert err.code == ErrorCode.DEPENDENCY_UNAVAILABLE
    assert err.status == 0
    assert "http://test" in err.detail
