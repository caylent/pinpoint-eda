"""Tests for CLI interface."""

import click
import pytest
from click.testing import CliRunner

from pinpoint_eda import __version__
from pinpoint_eda.cli import _build_accounts, cli


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
        assert "--role-arn" in result.output
        assert "--external-id" in result.output
        assert "--dry-run" in result.output

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


class TestBuildAccounts:
    def test_no_flags_returns_default(self):
        accounts = _build_accounts((), (), None)
        assert len(accounts) == 1
        assert accounts[0].profile is None
        assert accounts[0].role_arn is None

    def test_profiles_only(self):
        accounts = _build_accounts(("prod", "staging"), (), None)
        assert len(accounts) == 2
        assert accounts[0].profile == "prod"
        assert accounts[1].profile == "staging"
        assert accounts[0].role_arn is None

    def test_role_arns_only(self):
        accounts = _build_accounts((), ("arn:aws:iam::111:role/A", "arn:aws:iam::222:role/B"), None)
        assert len(accounts) == 2
        assert accounts[0].role_arn == "arn:aws:iam::111:role/A"
        assert accounts[1].role_arn == "arn:aws:iam::222:role/B"
        assert accounts[0].profile is None

    def test_role_arns_with_external_id(self):
        accounts = _build_accounts((), ("arn:aws:iam::111:role/A",), "my-ext-id")
        assert len(accounts) == 1
        assert accounts[0].external_id == "my-ext-id"

    def test_one_profile_plus_role_arns(self):
        accounts = _build_accounts(
            ("hub",), ("arn:aws:iam::111:role/A", "arn:aws:iam::222:role/B"), "ext"
        )
        assert len(accounts) == 2
        assert accounts[0].profile == "hub"
        assert accounts[0].role_arn == "arn:aws:iam::111:role/A"
        assert accounts[0].external_id == "ext"
        assert accounts[1].profile == "hub"
        assert accounts[1].role_arn == "arn:aws:iam::222:role/B"

    def test_multiple_profiles_plus_role_arns_errors(self):
        with pytest.raises(click.UsageError, match="Cannot combine multiple"):
            _build_accounts(("a", "b"), ("arn:aws:iam::111:role/A",), None)
