"""Tests for rate limiter."""

import threading

import pytest
from botocore.exceptions import ClientError

from pinpoint_eda.exceptions import RateLimitExceededError
from pinpoint_eda.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_acquire_basic(self):
        limiter = RateLimiter(requests_per_second=100.0)
        limiter.acquire()
        assert limiter.total_calls == 1

    def test_acquire_multiple(self):
        limiter = RateLimiter(requests_per_second=100.0)
        for _ in range(10):
            limiter.acquire()
        assert limiter.total_calls == 10

    def test_call_with_retry_success(self):
        limiter = RateLimiter(requests_per_second=100.0)
        result = limiter.call_with_retry(lambda: 42)
        assert result == 42

    def test_call_with_retry_non_throttle_error(self):
        limiter = RateLimiter(requests_per_second=100.0)

        def fail():
            raise ClientError(
                {"Error": {"Code": "NotFoundException", "Message": "not found"},
                 "ResponseMetadata": {"HTTPStatusCode": 404}},
                "GetApp",
            )

        with pytest.raises(ClientError):
            limiter.call_with_retry(fail)

    def test_call_with_retry_throttle_then_success(self):
        limiter = RateLimiter(requests_per_second=100.0)
        call_count = 0

        def intermittent():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ClientError(
                    {"Error": {"Code": "ThrottlingException", "Message": "slow down"},
                     "ResponseMetadata": {"HTTPStatusCode": 429}},
                    "GetSegments",
                )
            return "success"

        result = limiter.call_with_retry(intermittent)
        assert result == "success"
        assert call_count == 3

    def test_call_with_retry_max_retries_exceeded(self):
        limiter = RateLimiter(requests_per_second=1000.0)

        def always_throttle():
            raise ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "slow down"},
                 "ResponseMetadata": {"HTTPStatusCode": 429}},
                "GetSegments",
            )

        with pytest.raises(RateLimitExceededError):
            limiter.call_with_retry(always_throttle)

    def test_throughput(self):
        limiter = RateLimiter(requests_per_second=1000.0)
        for _ in range(100):
            limiter.acquire()
        assert limiter.throughput > 0

    def test_thread_safety(self):
        limiter = RateLimiter(requests_per_second=1000.0)
        errors = []

        def acquire_many():
            try:
                for _ in range(50):
                    limiter.acquire()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=acquire_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert limiter.total_calls == 250
