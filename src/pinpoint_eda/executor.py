"""Parallel scan executor using ThreadPoolExecutor."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ScanExecutor:
    """Manages thread-based parallelism for scanning operations."""

    def __init__(self, max_workers: int = 5) -> None:
        self._max_workers = max_workers
        self._shutdown_event = threading.Event()
        self._executor: ThreadPoolExecutor | None = None

    @property
    def should_stop(self) -> bool:
        return self._shutdown_event.is_set()

    def request_shutdown(self) -> None:
        """Signal all threads to stop gracefully."""
        self._shutdown_event.set()

    def map_parallel(
        self,
        func: Callable[..., T],
        items: list[Any],
        max_workers: int | None = None,
    ) -> list[tuple[Any, T | None, Exception | None]]:
        """Execute func for each item in parallel, returning (item, result, error) tuples.

        Results are returned in completion order.
        """
        workers = max_workers or self._max_workers
        results: list[tuple[Any, T | None, Exception | None]] = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            self._executor = executor
            future_to_item: dict[Future, Any] = {}

            for item in items:
                if self._shutdown_event.is_set():
                    break
                future = executor.submit(func, item)
                future_to_item[future] = item

            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result = future.result()
                    results.append((item, result, None))
                except Exception as e:
                    logger.error("Error processing %s: %s", item, e)
                    results.append((item, None, e))

            self._executor = None

        return results

    def shutdown(self) -> None:
        """Force shutdown the executor."""
        self._shutdown_event.set()
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
