"""Click CLI application for Pinpoint EDA."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from pinpoint_eda import __version__
from pinpoint_eda.config import AccountConfig, ScanConfig

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="pinpoint-eda")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Pinpoint EDA - Migration Assessment CLI for Amazon Pinpoint.

    Run with no arguments to launch the interactive configurator.
    """
    ctx.ensure_object(dict)
    if ctx.invoked_subcommand is None:
        from pinpoint_eda.configurator import run_configurator

        config = run_configurator()
        if config is None:
            raise SystemExit(0)
        _run_scan(config)


@cli.command()
@click.option("--profile", "-p", multiple=True, help="AWS profile (repeatable).")
@click.option("--region", "-r", multiple=True, help="AWS region (repeatable, skip auto-discover).")
@click.option("--role-arn", default=None, help="IAM role ARN for cross-account access.")
@click.option("--app-id", "-a", multiple=True, help="Specific app ID(s) to scan (repeatable).")
@click.option("--scanner", "-s", multiple=True, help="Specific scanner(s) to run (repeatable).")
@click.option(
    "--max-workers", "-w", default=5, type=int, help="Max parallel threads.", show_default=True
)
@click.option(
    "--kpi-days", default=90, type=int, help="KPI history window in days.", show_default=True
)
@click.option(
    "--output", "-o", default="./pinpoint-eda-output", type=click.Path(),
    help="Output directory.", show_default=True,
)
@click.option("--resume", is_flag=True, help="Resume an interrupted scan.")
@click.option("--fresh", is_flag=True, help="Discard checkpoint, start fresh.")
@click.option("--json-only", is_flag=True, help="JSON output only (no Rich display).")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.option("--no-sms-voice-v2", is_flag=True, help="Skip PinpointSMSVoiceV2 scanning.")
def scan(
    profile: tuple[str, ...],
    region: tuple[str, ...],
    role_arn: str | None,
    app_id: tuple[str, ...],
    scanner: tuple[str, ...],
    max_workers: int,
    kpi_days: int,
    output: str,
    resume: bool,
    fresh: bool,
    json_only: bool,
    verbose: bool,
    no_sms_voice_v2: bool,
) -> None:
    """Run a Pinpoint migration assessment scan."""
    accounts = []
    if role_arn:
        accounts.append(AccountConfig(role_arn=role_arn))
    if profile:
        for p in profile:
            accounts.append(AccountConfig(profile=p))
    if not accounts:
        accounts.append(AccountConfig())

    config = ScanConfig(
        accounts=accounts,
        regions=list(region),
        app_ids=list(app_id),
        scanners=list(scanner),
        max_workers=max_workers,
        kpi_days=kpi_days,
        output_dir=Path(output),
        resume=resume,
        fresh=fresh,
        json_only=json_only,
        verbose=verbose,
        no_sms_voice_v2=no_sms_voice_v2,
    )
    _run_scan(config)


@cli.command("list-scanners")
def list_scanners() -> None:
    """Show available scanners and their descriptions."""
    from rich.table import Table

    from pinpoint_eda.scanners import SCANNER_REGISTRY

    table = Table(title="Available Scanners", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Scope", style="green")

    for name, meta in sorted(SCANNER_REGISTRY.items()):
        scope = "per-app" if meta.per_app else "account-level"
        table.add_row(name, meta.description, scope)

    console.print(table)


@cli.command("report")
@click.argument("file", type=click.Path(exists=True))
def report(file: str) -> None:
    """Re-render a previously generated JSON report."""
    from pinpoint_eda.report import render_report_from_file

    render_report_from_file(Path(file), console)


def _run_scan(config: ScanConfig) -> None:
    """Execute the scan with the given config."""
    from pinpoint_eda._orchestrator import Orchestrator

    orchestrator = Orchestrator(config, console)
    orchestrator.run()
