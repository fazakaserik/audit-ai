"""API test fixtures."""

from __future__ import annotations

import pytest

from backend.application.api.dependencies import get_bound
from backend.application.api.main import create_app
from support.test_container import build_fakes_bound, build_test_container


@pytest.fixture
def bound():
    return build_fakes_bound()


@pytest.fixture
def test_app(bound):
    container = build_test_container()
    app = create_app(settings=container.settings, container=container)

    async def override_bound():
        return bound

    app.dependency_overrides[get_bound] = override_bound
    return app
