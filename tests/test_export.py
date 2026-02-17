"""Tests for CSV export."""

import csv
import json

from rich.console import Console

from pinpoint_eda.export import export_csv


def _make_report() -> dict:
    """Build a minimal report for testing."""
    return {
        "metadata": {
            "tool_version": "0.0.1",
            "generated_at": "2026-02-17T00:00:00+00:00",
            "pinpoint_eol": "2026-10-30",
            "days_until_eol": 255,
            "scan_duration_seconds": 5.0,
            "api_calls": 10,
            "error_count": 0,
            "config": {
                "accounts": [{"label": "test"}],
                "regions": ["us-east-1"],
                "scanners": ["all"],
                "max_workers": 5,
                "kpi_days": 90,
            },
        },
        "complexity": {
            "overall_score": 7,
            "overall_level": "LOW",
            "app_assessments": [
                {
                    "app_id": "app-1",
                    "app_name": "MyApp",
                    "region": "us-east-1",
                    "total_score": 4,
                    "level": "LOW",
                    "is_active": True,
                    "factors": [
                        {
                            "name": "Active Channels",
                            "score": 2,
                            "explanation": "1 active: SMS.",
                            "migration_target": "Various (SES, SNS, Connect)",
                        },
                        {
                            "name": "Campaigns",
                            "score": 2,
                            "explanation": "1 campaign (1 active).",
                            "migration_target": "Amazon Connect Outbound Campaigns",
                        },
                    ],
                },
            ],
            "account_assessments": [
                {
                    "region": "us-east-1",
                    "total_score": 3,
                    "factors": [
                        {
                            "name": "Templates",
                            "score": 3,
                            "explanation": "3 templates.",
                            "migration_target": "Amazon SES Templates / Amazon Connect",
                        },
                    ],
                },
            ],
            "migration_targets": {},
        },
        "inventory": {
            "test:us-east-1": {
                "app-1": {
                    "applications": {
                        "resource_count": 1,
                        "metadata": {"name": "MyApp", "tags": {}},
                        "errors": [],
                    },
                    "channels": {
                        "resource_count": 1,
                        "metadata": {
                            "active_channels": ["SMS"],
                            "active_count": 1,
                        },
                        "errors": [],
                    },
                    "campaigns": {
                        "resource_count": 1,
                        "metadata": {
                            "total": 1,
                            "active": 1,
                            "state_breakdown": {"ACTIVE": 1},
                        },
                        "errors": [],
                    },
                },
                "account": {
                    "templates": {
                        "resource_count": 3,
                        "metadata": {
                            "total": 3,
                            "type_breakdown": {"EMAIL": 2, "SMS": 1},
                        },
                        "errors": [],
                    },
                },
            },
        },
        "errors": [],
    }


class TestExportCSV:
    def test_creates_three_csv_files(self, tmp_path):
        report_path = tmp_path / "report.json"
        report_path.write_text(json.dumps(_make_report()))

        console = Console(file=open("/dev/null", "w"))
        export_csv(report_path, tmp_path / "csv_out", console)

        assert (tmp_path / "csv_out" / "applications.csv").exists()
        assert (tmp_path / "csv_out" / "inventory.csv").exists()
        assert (tmp_path / "csv_out" / "account_resources.csv").exists()

    def test_applications_csv_content(self, tmp_path):
        report_path = tmp_path / "report.json"
        report_path.write_text(json.dumps(_make_report()))

        console = Console(file=open("/dev/null", "w"))
        export_csv(report_path, tmp_path, console)

        with open(tmp_path / "applications.csv") as f:
            reader = list(csv.DictReader(f))

        assert len(reader) == 1
        row = reader[0]
        assert row["app_id"] == "app-1"
        assert row["app_name"] == "MyApp"
        assert row["complexity_score"] == "4"
        assert row["complexity_level"] == "LOW"
        assert row["is_active"] == "True"
        assert "Active Channels" in row["top_factors"]

    def test_inventory_csv_content(self, tmp_path):
        report_path = tmp_path / "report.json"
        report_path.write_text(json.dumps(_make_report()))

        console = Console(file=open("/dev/null", "w"))
        export_csv(report_path, tmp_path, console)

        with open(tmp_path / "inventory.csv") as f:
            reader = list(csv.DictReader(f))

        # 3 scanners for app-1 (applications, channels, campaigns) -- account excluded
        assert len(reader) == 3
        scanner_names = {row["scanner"] for row in reader}
        assert scanner_names == {"applications", "channels", "campaigns"}

        # Check a specific row
        channels_row = next(r for r in reader if r["scanner"] == "channels")
        assert channels_row["resource_count"] == "1"
        assert channels_row["app_name"] == "MyApp"

    def test_account_resources_csv(self, tmp_path):
        report_path = tmp_path / "report.json"
        report_path.write_text(json.dumps(_make_report()))

        console = Console(file=open("/dev/null", "w"))
        export_csv(report_path, tmp_path, console)

        with open(tmp_path / "account_resources.csv") as f:
            reader = list(csv.DictReader(f))

        assert len(reader) == 1
        row = reader[0]
        assert row["scanner"] == "templates"
        assert row["resource_count"] == "3"
        assert "Templates" in row["factors"]

    def test_export_to_custom_output_dir(self, tmp_path):
        report_path = tmp_path / "report.json"
        report_path.write_text(json.dumps(_make_report()))

        out = tmp_path / "custom" / "nested"
        console = Console(file=open("/dev/null", "w"))
        export_csv(report_path, out, console)

        assert (out / "applications.csv").exists()

    def test_empty_report(self, tmp_path):
        """Export handles a report with no apps gracefully."""
        report = _make_report()
        report["complexity"]["app_assessments"] = []
        report["complexity"]["account_assessments"] = []
        report["inventory"] = {}

        report_path = tmp_path / "report.json"
        report_path.write_text(json.dumps(report))

        console = Console(file=open("/dev/null", "w"))
        export_csv(report_path, tmp_path, console)

        with open(tmp_path / "applications.csv") as f:
            reader = list(csv.DictReader(f))
        assert len(reader) == 0
