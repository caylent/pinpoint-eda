"""Tests for report generation."""

import json

from rich.console import Console

from pinpoint_eda.complexity import assess_complexity
from pinpoint_eda.config import ScanConfig
from pinpoint_eda.report import generate_report, render_report_from_file
from pinpoint_eda.scanners.base import ScanResult


class TestGenerateReport:
    def test_generates_json_file(self, tmp_path):
        config = ScanConfig(output_dir=tmp_path, json_only=True)
        results = {
            "default:us-east-1": [
                ScanResult(
                    scanner_name="applications",
                    region="us-east-1",
                    app_id="app-1",
                    resource_count=1,
                    metadata={"name": "TestApp"},
                ),
            ]
        }
        complexity = assess_complexity(results)
        console = Console(file=open("/dev/null", "w"))

        generate_report(
            results=results,
            complexity=complexity,
            config=config,
            scan_duration=5.0,
            api_calls=42,
            errors=[],
            console=console,
        )

        json_path = tmp_path / "pinpoint-eda-report.json"
        assert json_path.exists()

        with open(json_path) as f:
            data = json.load(f)

        assert "metadata" in data
        assert "complexity" in data
        assert "inventory" in data
        assert data["metadata"]["api_calls"] == 42
        assert data["metadata"]["scan_duration_seconds"] == 5.0

    def test_render_from_file(self, tmp_path):
        # Generate a report first
        config = ScanConfig(output_dir=tmp_path, json_only=True)
        results = {
            "default:us-east-1": [
                ScanResult(
                    scanner_name="applications",
                    region="us-east-1",
                    app_id="app-1",
                    resource_count=1,
                    metadata={"name": "TestApp"},
                ),
            ]
        }
        complexity = assess_complexity(results)
        console = Console(file=open("/dev/null", "w"))

        generate_report(
            results=results,
            complexity=complexity,
            config=config,
            scan_duration=5.0,
            api_calls=42,
            errors=[],
            console=console,
        )

        # Re-render from file -- should not raise
        json_path = tmp_path / "pinpoint-eda-report.json"
        render_report_from_file(json_path, console)
