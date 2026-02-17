"""Tests for checkpoint manager."""


import pytest

from pinpoint_eda.checkpoint import CheckpointManager
from pinpoint_eda.exceptions import ConfigMismatchError


class TestCheckpointManager:
    def test_initialize_fresh(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "hash123")
        mgr.initialize()
        assert mgr.run_id
        assert (tmp_path / ".pinpoint-eda-checkpoint.json").exists()

    def test_mark_completed(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "hash123")
        mgr.initialize()

        mgr.mark_in_progress("segments:us-east-1:app-123")
        mgr.mark_completed("segments:us-east-1:app-123", 45)

        assert mgr.is_completed("segments:us-east-1:app-123")
        assert not mgr.is_completed("campaigns:us-east-1:app-123")

    def test_mark_error(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "hash123")
        mgr.initialize()

        mgr.mark_in_progress("segments:us-east-1:app-123")
        mgr.mark_error("segments:us-east-1:app-123", "access denied")

        assert len(mgr.errors) == 1
        assert mgr.errors[0]["error"] == "access denied"

    def test_resume(self, tmp_path):
        # First run
        mgr1 = CheckpointManager(tmp_path, "hash123")
        mgr1.initialize()
        run_id = mgr1.run_id
        mgr1.mark_completed("segments:us-east-1:app-123", 45)

        # Resume
        mgr2 = CheckpointManager(tmp_path, "hash123")
        mgr2.initialize(resume=True)
        assert mgr2.run_id == run_id
        assert mgr2.is_completed("segments:us-east-1:app-123")

    def test_resume_config_mismatch(self, tmp_path):
        mgr1 = CheckpointManager(tmp_path, "hash123")
        mgr1.initialize()

        mgr2 = CheckpointManager(tmp_path, "different_hash")
        with pytest.raises(ConfigMismatchError):
            mgr2.initialize(resume=True)

    def test_discovered_regions(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "hash123")
        mgr.initialize()

        regions = {"us-east-1": ["app-1", "app-2"], "eu-west-1": ["app-3"]}
        mgr.set_discovered_regions(regions)

        assert mgr.get_discovered_regions() == regions

    def test_scan_results_storage(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "hash123")
        mgr.initialize()

        result = {"scanner_name": "segments", "resource_count": 10}
        mgr.mark_completed("segments:us-east-1:app-1", 10, result=result)

        stored = mgr.get_scan_results()
        assert "segments:us-east-1:app-1" in stored
        assert stored["segments:us-east-1:app-1"]["resource_count"] == 10

    def test_cleanup(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "hash123")
        mgr.initialize()
        assert (tmp_path / ".pinpoint-eda-checkpoint.json").exists()

        mgr.cleanup()
        assert not (tmp_path / ".pinpoint-eda-checkpoint.json").exists()

    def test_atomic_write(self, tmp_path):
        """Verify no .tmp files are left behind."""
        mgr = CheckpointManager(tmp_path, "hash123")
        mgr.initialize()
        mgr.mark_completed("test:key:1", 5)

        # No tmp files should remain
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0
