"""Tests for CLI interface."""

from click.testing import CliRunner

from pinpoint_eda import __version__
from pinpoint_eda.cli import cli


class TestCLI:
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Migration Assessment" in result.output

    def test_scan_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--profile" in result.output
        assert "--region" in result.output
        assert "--max-workers" in result.output

    def test_list_scanners(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["list-scanners"])
        assert result.exit_code == 0
        assert "segments" in result.output.lower()
        assert "campaigns" in result.output.lower()
        assert "journeys" in result.output.lower()

    def test_report_missing_file(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "/nonexistent/file.json"])
        assert result.exit_code != 0
