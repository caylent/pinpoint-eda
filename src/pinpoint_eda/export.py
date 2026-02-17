"""CSV export from a pinpoint-eda JSON report."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from rich.console import Console

logger = logging.getLogger(__name__)


def export_csv(report_path: Path, output_dir: Path, console: Console) -> None:
    """Export a JSON report to CSV files.

    Produces:
      - applications.csv  -- one row per app with complexity scores
      - inventory.csv     -- one row per app+scanner with resource counts and metadata
      - account_resources.csv -- account-level resources per region
    """
    with open(report_path) as f:
        report = json.load(f)

    output_dir.mkdir(parents=True, exist_ok=True)

    apps_path = output_dir / "applications.csv"
    _write_applications_csv(report, apps_path)
    console.print(f"  [green]Wrote[/] {apps_path}")

    inv_path = output_dir / "inventory.csv"
    _write_inventory_csv(report, inv_path)
    console.print(f"  [green]Wrote[/] {inv_path}")

    acct_path = output_dir / "account_resources.csv"
    _write_account_csv(report, acct_path)
    console.print(f"  [green]Wrote[/] {acct_path}")


def _write_applications_csv(report: dict[str, Any], path: Path) -> None:
    """One row per application with complexity assessment."""
    complexity = report.get("complexity", {})
    app_assessments = complexity.get("app_assessments", [])

    fieldnames = [
        "region", "app_id", "app_name", "is_active",
        "complexity_score", "complexity_level", "top_factors",
        "migration_notes",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for app in app_assessments:
            factors = app.get("factors", [])
            top = "; ".join(
                f"{fa['name']} ({fa['score']}pts)" for fa in factors[:5]
            )
            targets = "; ".join(
                fa["migration_target"] for fa in factors if fa.get("migration_target")
            )
            writer.writerow({
                "region": app["region"],
                "app_id": app["app_id"],
                "app_name": app["app_name"],
                "is_active": app.get("is_active", False),
                "complexity_score": app["total_score"],
                "complexity_level": app["level"],
                "top_factors": top,
                "migration_notes": targets,
            })


def _write_inventory_csv(report: dict[str, Any], path: Path) -> None:
    """One row per app+scanner with resource counts and flattened metadata."""
    inventory = report.get("inventory", {})

    # Collect all metadata keys across all scanners to build columns
    all_meta_keys: set[str] = set()
    rows: list[dict[str, Any]] = []

    for region_key, apps in inventory.items():
        for app_id, scanners in apps.items():
            if app_id == "account":
                continue
            # Resolve app name from applications scanner
            app_name = app_id
            app_scanner = scanners.get("applications", {})
            if app_scanner.get("metadata", {}).get("name"):
                app_name = app_scanner["metadata"]["name"]

            for scanner_name, data in scanners.items():
                meta = data.get("metadata", {})
                flat_meta = _flatten_metadata(meta)
                all_meta_keys.update(flat_meta.keys())
                rows.append({
                    "region_key": region_key,
                    "app_id": app_id,
                    "app_name": app_name,
                    "scanner": scanner_name,
                    "resource_count": data.get("resource_count", 0),
                    "errors": "; ".join(data.get("errors", [])),
                    **flat_meta,
                })

    # Stable column order: fixed columns first, then sorted metadata columns
    fixed = ["region_key", "app_id", "app_name", "scanner", "resource_count", "errors"]
    meta_cols = sorted(all_meta_keys - set(fixed))
    fieldnames = fixed + meta_cols

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_account_csv(report: dict[str, Any], path: Path) -> None:
    """Account-level resources (templates, recommenders, SMS/Voice V2)."""
    inventory = report.get("inventory", {})
    complexity = report.get("complexity", {})

    # Also pull in account assessment scores
    acct_scores: dict[str, dict] = {}
    for acct in complexity.get("account_assessments", []):
        acct_scores[acct["region"]] = acct

    fieldnames = [
        "region_key", "scanner", "resource_count",
        "complexity_score", "factors", "metadata",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for region_key, apps in inventory.items():
            account_data = apps.get("account", {})
            if not account_data:
                continue

            # Parse region from key (e.g., "131578276461:us-east-1" -> "us-east-1")
            parts = region_key.split(":", 1)
            region = parts[1] if len(parts) > 1 else region_key

            acct_assessment = acct_scores.get(region, {})
            factors_str = "; ".join(
                f"{fa['name']} ({fa['score']}pts)"
                for fa in acct_assessment.get("factors", [])
            )

            for scanner_name, data in account_data.items():
                meta = data.get("metadata", {})
                writer.writerow({
                    "region_key": region_key,
                    "scanner": scanner_name,
                    "resource_count": data.get("resource_count", 0),
                    "complexity_score": acct_assessment.get("total_score", 0),
                    "factors": factors_str,
                    "metadata": json.dumps(meta, default=str),
                })


def _flatten_metadata(meta: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten nested metadata dict for CSV columns.

    Skips complex nested structures (lists of dicts) and converts
    simple values to strings.
    """
    result: dict[str, str] = {}
    for key, value in meta.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            # Flatten one level of dicts (e.g., state_breakdown)
            for k, v in value.items():
                result[f"{full_key}.{k}"] = str(v)
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                # Skip complex nested lists (journey_complexities, etc.)
                result[full_key] = f"[{len(value)} items]"
            else:
                result[full_key] = "; ".join(str(v) for v in value)
        else:
            result[full_key] = str(value)
    return result
