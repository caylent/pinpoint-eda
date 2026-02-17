"""JSON checkpoint for scan resume on ctrl+c."""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pinpoint_eda.exceptions import CheckpointError, ConfigMismatchError

logger = logging.getLogger(__name__)

CHECKPOINT_FILENAME = ".pinpoint-eda-checkpoint.json"


class CheckpointManager:
    """Thread-safe checkpoint manager with atomic writes."""

    def __init__(self, output_dir: Path, config_hash: str) -> None:
        self._output_dir = output_dir
        self._config_hash = config_hash
        self._lock = threading.Lock()
        self._filepath = output_dir / CHECKPOINT_FILENAME
        self._state: dict[str, Any] = {}
        self._dirty = False

    def initialize(self, resume: bool = False) -> None:
        """Initialize checkpoint state. Load existing if resume=True."""
        self._output_dir.mkdir(parents=True, exist_ok=True)

        if resume and self._filepath.exists():
            self._load()
            if self._state.get("config_hash") != self._config_hash:
                raise ConfigMismatchError(
                    "Checkpoint config hash doesn't match current scan config. "
                    "Use --fresh to discard the checkpoint."
                )
            logger.info("Resumed checkpoint: %s", self._state.get("run_id"))
        else:
            self._state = {
                "run_id": str(uuid.uuid4()),
                "started_at": datetime.now(UTC).isoformat(),
                "config_hash": self._config_hash,
                "discovered_regions": {},
                "completed": {},
                "in_progress": [],
                "errors": [],
                "scan_results": {},
            }
            self._save()

    def _load(self) -> None:
        """Load checkpoint from disk."""
        try:
            with open(self._filepath) as f:
                self._state = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise CheckpointError(f"Failed to load checkpoint: {e}") from e

    def _save(self) -> None:
        """Atomic write: write to tmp file, then rename."""
        tmp_path = self._filepath.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as f:
                json.dump(self._state, f, indent=2, default=str)
            os.replace(tmp_path, self._filepath)
        except OSError as e:
            raise CheckpointError(f"Failed to save checkpoint: {e}") from e

    def set_discovered_regions(self, regions: dict[str, list[str]]) -> None:
        """Record discovered regions and their app IDs."""
        with self._lock:
            self._state["discovered_regions"] = regions
            self._save()

    def get_discovered_regions(self) -> dict[str, list[str]]:
        """Return previously discovered regions, if any."""
        with self._lock:
            return self._state.get("discovered_regions", {})

    def mark_in_progress(self, key: str) -> None:
        """Mark a scanner+region+app as in progress."""
        with self._lock:
            in_progress = self._state.get("in_progress", [])
            if key not in in_progress:
                in_progress.append(key)
                self._state["in_progress"] = in_progress
                self._save()

    def mark_completed(self, key: str, resource_count: int, result: Any = None) -> None:
        """Mark a scanner+region+app as completed."""
        with self._lock:
            in_progress = self._state.get("in_progress", [])
            if key in in_progress:
                in_progress.remove(key)
            self._state["completed"][key] = {
                "resource_count": resource_count,
                "completed_at": datetime.now(UTC).isoformat(),
            }
            if result is not None:
                self._state.setdefault("scan_results", {})[key] = result
            self._save()

    def mark_error(self, key: str, error: str) -> None:
        """Record an error for a scanner+region+app."""
        with self._lock:
            in_progress = self._state.get("in_progress", [])
            if key in in_progress:
                in_progress.remove(key)
            self._state["errors"].append({
                "key": key,
                "error": error,
                "timestamp": datetime.now(UTC).isoformat(),
            })
            self._save()

    def is_completed(self, key: str) -> bool:
        """Check if a scanner+region+app has already been completed."""
        with self._lock:
            return key in self._state.get("completed", {})

    def get_scan_results(self) -> dict[str, Any]:
        """Return all stored scan results."""
        with self._lock:
            return dict(self._state.get("scan_results", {}))

    @property
    def run_id(self) -> str:
        return self._state.get("run_id", "")

    @property
    def errors(self) -> list[dict]:
        with self._lock:
            return list(self._state.get("errors", []))

    @property
    def completed_count(self) -> int:
        with self._lock:
            return len(self._state.get("completed", {}))

    def cleanup(self) -> None:
        """Remove checkpoint file after successful completion."""
        try:
            if self._filepath.exists():
                self._filepath.unlink()
        except OSError:
            pass
