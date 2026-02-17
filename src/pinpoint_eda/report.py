"""JSON and console report generation."""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from pinpoint_eda import __version__
from pinpoint_eda.complexity import (
    MIGRATION_TARGETS,
    AccountComplexity,
    ComplexityAssessment,
    ComplexityLevel,
)
from pinpoint_eda.config import ScanConfig
from pinpoint_eda.scanners.base import ScanResult

logger = logging.getLogger(__name__)

PINPOINT_EOL = date(2026, 10, 30)

LEVEL_COLORS = {
    ComplexityLevel.LOW: "green",
    ComplexityLevel.MEDIUM: "yellow",
    ComplexityLevel.HIGH: "red",
    ComplexityLevel.VERY_HIGH: "bold red",
}


def generate_report(
    results: dict[str, list[ScanResult]],
    complexity: ComplexityAssessment,
    config: ScanConfig,
    scan_duration: float,
    api_calls: int,
    errors: list[dict],
    console: Console,
    account_ids: dict[str, str] | None = None,
) -> None:
    """Generate JSON report and optionally render console summary."""
    report_data = _build_report_data(
        results, complexity, config, scan_duration, api_calls, errors,
        account_ids=account_ids,
    )

    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "pinpoint-eda-report.json"
    with open(json_path, "w") as f:
        json.dump(report_data, f, indent=2, default=str)

    if not config.json_only:
        _render_console_summary(report_data, complexity, console)

    console.print(f"\n[bold green]Report saved to:[/] {json_path}")


def render_report_from_file(file_path: Path, console: Console) -> None:
    """Re-render a previously saved JSON report."""
    with open(file_path) as f:
        report_data = json.load(f)

    from pinpoint_eda.complexity import AppComplexity, ComplexityFactor

    complexity_data = report_data.get("complexity", {})
    app_assessments = []
    for app_data in complexity_data.get("app_assessments", []):
        factors = [
            ComplexityFactor(
                name=f["name"],
                score=f["score"],
                explanation=f["explanation"],
                migration_target=f.get("migration_target", ""),
            )
            for f in app_data.get("factors", [])
        ]
        app_assessments.append(AppComplexity(
            app_id=app_data["app_id"],
            app_name=app_data["app_name"],
            region=app_data["region"],
            total_score=app_data["total_score"],
            level=ComplexityLevel(app_data["level"]),
            factors=factors,
            is_active=app_data.get("is_active", False),
        ))

    account_assessments = []
    for acct_data in complexity_data.get("account_assessments", []):
        factors = [
            ComplexityFactor(
                name=f["name"],
                score=f["score"],
                explanation=f["explanation"],
                migration_target=f.get("migration_target", ""),
            )
            for f in acct_data.get("factors", [])
        ]
        account_assessments.append(AccountComplexity(
            region=acct_data["region"],
            total_score=acct_data["total_score"],
            factors=factors,
        ))

    complexity = ComplexityAssessment(
        overall_score=complexity_data.get("overall_score", 0),
        overall_level=ComplexityLevel(
            complexity_data.get("overall_level", "LOW")
        ),
        app_assessments=app_assessments,
        account_assessments=account_assessments,
        migration_targets=complexity_data.get("migration_targets", {}),
    )

    _render_console_summary(report_data, complexity, console)


def _build_report_data(
    results: dict[str, list[ScanResult]],
    complexity: ComplexityAssessment,
    config: ScanConfig,
    scan_duration: float,
    api_calls: int,
    errors: list[dict],
    account_ids: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the full JSON report data structure."""
    days_remaining = (PINPOINT_EOL - date.today()).days

    inventory: dict[str, Any] = {}
    for region_key, scan_results in results.items():
        region_data: dict[str, Any] = {}
        for r in scan_results:
            app_key = r.app_id
            if app_key not in region_data:
                region_data[app_key] = {}
            region_data[app_key][r.scanner_name] = {
                "resource_count": r.resource_count,
                "metadata": r.metadata,
                "errors": r.errors,
            }
        inventory[region_key] = region_data

    # Build account info with resolved IDs
    account_ids = account_ids or {}
    accounts_info = []
    for a in config.accounts:
        acct_info: dict[str, str] = {"label": a.label}
        resolved = account_ids.get(a.label)
        if resolved:
            acct_info["account_id"] = resolved
        accounts_info.append(acct_info)

    return {
        "metadata": {
            "tool_version": __version__,
            "generated_at": datetime.now(UTC).isoformat(),
            "pinpoint_eol": PINPOINT_EOL.isoformat(),
            "days_until_eol": days_remaining,
            "scan_duration_seconds": round(scan_duration, 1),
            "api_calls": api_calls,
            "error_count": len(errors),
            "config": {
                "accounts": accounts_info,
                "regions": config.regions or ["auto-discovered"],
                "scanners": config.scanners or ["all"],
                "max_workers": config.max_workers,
                "kpi_days": config.kpi_days,
            },
        },
        "complexity": complexity.to_dict(),
        "inventory": inventory,
        "errors": errors,
    }


def _render_console_summary(
    report_data: dict[str, Any],
    complexity: ComplexityAssessment,
    console: Console,
) -> None:
    """Render the Rich console summary."""
    metadata = report_data.get("metadata", {})

    # EOL countdown panel
    days_remaining = metadata.get("days_until_eol", 0)
    if days_remaining > 180:
        eol_style = "green"
    elif days_remaining > 90:
        eol_style = "yellow"
    else:
        eol_style = "bold red"

    eol_text = Text()
    eol_text.append("Amazon Pinpoint End of Support: ", style="bold")
    eol_text.append("October 30, 2026\n", style=eol_style)
    eol_text.append(f"{days_remaining} days remaining", style=eol_style)

    console.print()
    console.print(Panel(
        eol_text, title="EOL Timeline", border_style=eol_style
    ))

    # Overall complexity
    overall_color = LEVEL_COLORS.get(complexity.overall_level, "white")
    console.print()
    console.print(Panel(
        Text.assemble(
            ("Overall Migration Complexity: ", "bold"),
            (f"{complexity.overall_level.value}", f"bold {overall_color}"),
            (f" (score: {complexity.overall_score})", "dim"),
        ),
        border_style=overall_color,
    ))

    # Scoring guide
    console.print()
    guide = Table(
        title="Scoring Guide",
        show_header=True, show_lines=False,
        title_style="bold",
    )
    guide.add_column("Resource", style="cyan")
    guide.add_column("Points", justify="right")
    guide.add_column("How It's Calculated", style="dim")

    guide.add_row(
        "Journeys", "varies",
        "State (active=5, done=3, draft=1) + activities + 2/branch + 3/integration",
    )
    guide.add_row("Campaigns", "3/active, 1/other", "Active campaigns need careful cutover")
    guide.add_row("Segments", "1 + 3/dyn + 2/imp", "Dynamic segments must be re-implemented")
    guide.add_row("Active Channels", "2 each", "Per enabled channel type (Email, SMS, etc.)")
    guide.add_row(
        "Push + Campaigns", "+5",
        "Push channels with active campaigns (no Connect equivalent)",
    )
    guide.add_row("Event Stream", "3-5", "5 if app has recent activity, 3 otherwise")
    guide.add_row("Campaign Hook", "5", "Lambda integration needs re-wiring")
    guide.add_row("Import Jobs", "2", "External data pipeline may need redirecting")
    guide.add_row("Templates", "1 each, in-app=8", "In-app templates have no AWS equivalent")
    guide.add_row("Recommenders", "5 each", "Custom ML integrations")
    guide.add_row("SMS/Voice V2", "2/phone, 2/pool, 3/reg", "Phone numbers, pools, registrations")

    guide.add_section()
    guide.add_row("[green]LOW[/]", "0-9", "Minimal migration effort")
    guide.add_row("[yellow]MEDIUM[/]", "10-29", "Moderate effort, plan 2-4 weeks")
    guide.add_row("[red]HIGH[/]", "30-69", "Significant effort, plan 1-2 months")
    guide.add_row("[bold red]VERY HIGH[/]", "70+", "Major undertaking, plan 2+ months")

    console.print(guide)
    console.print(
        "\n[dim]Scores are heuristic estimates to help prioritize migration planning. "
        "Actual effort depends on your team's familiarity with target services.[/]"
    )

    # Account-level resources table
    if complexity.account_assessments:
        console.print()
        acct_table = Table(
            title="Account-Level Resources (per region)",
            show_header=True, show_lines=True,
        )
        acct_table.add_column("Region", style="cyan")
        acct_table.add_column("Score", justify="right")
        acct_table.add_column("Factors")

        for acct in complexity.account_assessments:
            factor_lines = ", ".join(
                f"{f.name} ({f.score}pts)" for f in acct.factors
            )
            acct_table.add_row(
                acct.region,
                str(acct.total_score),
                factor_lines,
            )

        console.print(acct_table)

    # Per-application table
    if complexity.app_assessments:
        console.print()
        table = Table(
            title="Application Assessment",
            show_header=True, show_lines=True,
        )
        table.add_column("Application", style="bold")
        table.add_column("Region", style="cyan")
        table.add_column("Active?", justify="center")
        table.add_column("Score", justify="right")
        table.add_column("Level")
        table.add_column("Top Factors")

        for app in complexity.app_assessments:
            color = LEVEL_COLORS.get(app.level, "white")
            top_factors = ", ".join(
                f"{f.name} ({f.score}pts)" for f in app.factors[:3]
            )
            active_str = "[green]Yes[/]" if app.is_active else "[dim]No[/]"
            table.add_row(
                app.app_name,
                app.region,
                active_str,
                str(app.total_score),
                Text(app.level.value, style=color),
                top_factors,
            )

        console.print(table)

    # Migration target mapping tree
    console.print()
    tree = Tree("[bold]Migration Target Mapping")
    for key, target_info in MIGRATION_TARGETS.items():
        branch = tree.add(f"[cyan]{key}[/]")
        branch.add(f"[green]Target:[/] {target_info['target']}")
        branch.add(f"[dim]{target_info['notes']}[/]")

    console.print(tree)

    # Scan statistics
    console.print()
    stats_table = Table(title="Scan Statistics", show_header=False)
    stats_table.add_column("Metric", style="bold")
    stats_table.add_column("Value")

    duration = metadata.get("scan_duration_seconds", 0)
    stats_table.add_row("Duration", f"{duration:.1f}s")
    stats_table.add_row("API Calls", str(metadata.get("api_calls", 0)))
    stats_table.add_row("Errors", str(metadata.get("error_count", 0)))
    stats_table.add_row("Tool Version", metadata.get("tool_version", ""))

    console.print(stats_table)
