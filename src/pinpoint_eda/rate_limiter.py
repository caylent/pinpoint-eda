"""Thread-safe token-bucket rate limiter with adaptive backoff."""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

from botocore.exceptions import ClientError

from pinpoint_eda.exceptions import RateLimitExceededError

logger = logging.getLogger(__name__)

T = TypeVar("T")

THROTTLE_ERROR_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "Throttling",
    "RequestLimitExceeded",
    "ProvisionedThroughputExceededException",
}

MAX_RETRIES = 5
BASE_DELAY = 0.5


class RateLimiter:
    """Thread-safe token-bucket rate limiter with adaptive backoff."""

    def __init__(self, requests_per_second: float = 50.0) -> None:
        self._lock = threading.Lock()
        self._tokens = requests_per_second
        self._max_tokens = requests_per_second
        self._refill_rate = requests_per_second
        self._last_refill = time.monotonic()
        self._total_calls = 0
        self._total_retries = 0
        self._start_time = time.monotonic()

    def acquire(self) -> None:
        """Block until a token is available."""
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    self._total_calls += 1
                    return
            # No token available, sleep briefly and retry
            time.sleep(0.01)

    def _refill(self) -> None:
        """Refill tokens based on elapsed time. Must be called under lock."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    def call_with_retry(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Call with rate limiting + exponential backoff on throttling."""
        last_exception = None
        for attempt in range(MAX_RETRIES + 1):
            self.acquire()
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                status_code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
                is_throttle = error_code in THROTTLE_ERROR_CODES or status_code == 429
                is_server_error = status_code >= 500

                if not is_throttle and not is_server_error:
                    raise

                last_exception = e
                self._total_retries += 1

                if attempt < MAX_RETRIES:
                    delay = BASE_DELAY * (2**attempt)
                    jitter = random.uniform(0, delay)
                    logger.debug(
                        "Retryable error (attempt %d/%d), backoff %.2fs: %s",
                        attempt + 1,
                        MAX_RETRIES,
                        jitter,
                        error_code or f"HTTP {status_code}",
                    )
                    time.sleep(jitter)

        raise RateLimitExceededError(
            f"Rate limit exceeded after {MAX_RETRIES} retries"
        ) from last_exception

    @property
    def throughput(self) -> float:
        """Current throughput in calls per second."""
        elapsed = time.monotonic() - self._start_time
        if elapsed <= 0:
            return 0.0
        return self._total_calls / elapsed

    @property
    def total_calls(self) -> int:
        return self._total_calls

    @property
    def total_retries(self) -> int:
        return self._total_retries
