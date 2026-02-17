"""Abstract base scanner and scan result model."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pinpoint_eda.progress import ProgressDisplay
from pinpoint_eda.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Result from a single scanner run."""

    scanner_name: str
    region: str
    app_id: str
    resource_count: int = 0
    resources: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanner_name": self.scanner_name,
            "region": self.region,
            "app_id": self.app_id,
            "resource_count": self.resource_count,
            "resources": self.resources,
            "metadata": self.metadata,
            "errors": self.errors,
        }


class BaseScanner(ABC):
    """Abstract base class for all Pinpoint scanners."""

    name: str = ""
    description: str = ""
    per_app: bool = True  # Most scanners are per-app; templates/sms_voice_v2 are account-level

    def __init__(
        self,
        client: Any,
        rate_limiter: RateLimiter,
        region: str,
        app_id: str = "",
        progress: ProgressDisplay | None = None,
        kpi_days: int = 90,
    ) -> None:
        self.client = client
        self.rate_limiter = rate_limiter
        self.region = region
        self.app_id = app_id
        self.progress = progress
        self.kpi_days = kpi_days

    @abstractmethod
    def scan(self) -> ScanResult:
        """Execute the scan and return results."""

    def _update_status(self, message: str) -> None:
        """Update the progress display status line."""
        if self.progress:
            self.progress.update_status(message)

    def _increment_stat(self, name: str, count: int = 1) -> None:
        """Increment a running stat counter."""
        if self.progress:
            self.progress.increment_stat(name, count)
