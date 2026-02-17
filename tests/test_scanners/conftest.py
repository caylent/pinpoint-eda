"""Shared fixtures for scanner tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pinpoint_eda.rate_limiter import RateLimiter


@pytest.fixture
def rate_limiter():
    """A fast rate limiter for tests."""
    return RateLimiter(requests_per_second=10000.0)


@pytest.fixture
def mock_pinpoint_client():
    """A mock Pinpoint client."""
    return MagicMock()
