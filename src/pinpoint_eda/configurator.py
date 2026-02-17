"""Interactive questionary wizard for scan configuration."""

from __future__ import annotations

import configparser
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from pinpoint_eda.config import AccountConfig, ScanConfig
from pinpoint_eda.scanners import SCANNER_REGISTRY

console = Console()


def run_configurator() -> ScanConfig | None:
    """Launch interactive configuration wizard. Returns None if user cancels."""
    console.print()
    console.print(Panel(
        Text.assemble(
            ("Pinpoint EDA", "bold blue"),
            (" - Migration Assessment Wizard\n", "bold"),
            ("Configure your scan parameters below.", "dim"),
        ),
        border_style="blue",
    ))
    console.print()

    try:
        accounts = _configure_accounts()
        if accounts is None:
            return None

        regions = _configure_regions()
        scanners = _configure_scanners()
        options = _configure_options()

        config = ScanConfig(
            accounts=accounts,
            regions=regions,
            scanners=scanners,
            **options,
        )

        # Show summary and confirm
        if not _confirm_config(config):
            return None

        return config

    except KeyboardInterrupt:
        console.print("\n[yellow]Configuration cancelled.[/]")
        return None


def _discover_aws_profiles() -> list[str]:
    """Discover AWS profiles from ~/.aws/config and ~/.aws/credentials."""
    profiles: set[str] = set()

    config_path = Path.home() / ".aws" / "config"
    if config_path.exists():
        parser = configparser.ConfigParser()
        parser.read(config_path)
        for section in parser.sections():
            # Sections are "profile foo" or "default"
            if section.startswith("profile "):
                profiles.add(section.removeprefix("profile "))
            elif section == "default":
                profiles.add("default")

    creds_path = Path.home() / ".aws" / "credentials"
    if creds_path.exists():
        parser = configparser.ConfigParser()
        parser.read(creds_path)
        for section in parser.sections():
            profiles.add(section)

    return sorted(profiles)


def _configure_accounts() -> list[AccountConfig] | None:
    """Configure AWS account(s) to scan."""
    auth_method = questionary.select(
        "How do you want to authenticate?",
        choices=[
            questionary.Choice("AWS profile (from ~/.aws/config)", value="profile"),
            questionary.Choice("Default credentials (env vars / instance role)", value="default"),
            questionary.Choice("Cross-account role assumption", value="role"),
        ],
    ).ask()

    if auth_method is None:
        return None

    accounts = []

    if auth_method == "profile":
        discovered = _discover_aws_profiles()
        if discovered:
            choices = [
                questionary.Choice(p, value=p)
                for p in discovered
            ]
            selected = questionary.checkbox(
                "Select AWS profile(s) to scan (space to select, enter to confirm):",
                choices=choices,
            ).ask()
            if selected is None:
                return None
            if selected:
                return [AccountConfig(profile=p) for p in selected]
            # Empty selection -- fall through to manual entry

        # No profiles found or empty selection -- manual entry
        while True:
            profile = questionary.text(
                "AWS profile name:",
                default="default",
            ).ask()
            if profile is None:
                return None
            accounts.append(AccountConfig(profile=profile))

            add_more = questionary.confirm(
                "Add another profile?",
                default=False,
            ).ask()
            if not add_more:
                break

    elif auth_method == "role":
        # Offer a base profile for the role assumption
        discovered = _discover_aws_profiles()
        base_profile = None
        if discovered:
            use_profile = questionary.confirm(
                "Use an AWS profile as the base session for role assumption?",
                default=False,
            ).ask()
            if use_profile:
                base_profile = questionary.select(
                    "Base profile:",
                    choices=discovered,
                ).ask()

        while True:
            role_arn = questionary.text(
                "IAM Role ARN (arn:aws:iam::ACCOUNT:role/NAME):",
                validate=lambda x: (
                    x.startswith("arn:aws:iam:") or "Must be a valid IAM role ARN"
                ),
            ).ask()
            if role_arn is None:
                return None

            external_id = questionary.text(
                "External ID (optional, press Enter to skip):",
                default="",
            ).ask()

            accounts.append(AccountConfig(
                profile=base_profile,
                role_arn=role_arn,
                external_id=external_id or None,
            ))

            add_more = questionary.confirm(
                "Add another role?",
                default=False,
            ).ask()
            if not add_more:
                break

    else:
        accounts.append(AccountConfig())

    return accounts


def _configure_regions() -> list[str]:
    """Configure regions to scan."""
    discovery_mode = questionary.select(
        "Region selection:",
        choices=[
            questionary.Choice(
                "Auto-discover (probe all regions for Pinpoint apps)",
                value="auto",
            ),
            questionary.Choice("Specify region(s) manually", value="manual"),
        ],
    ).ask()

    if discovery_mode == "manual":
        regions_input = questionary.text(
            "Region(s) (comma-separated, e.g., us-east-1,eu-west-1):",
            default="us-east-1",
        ).ask()
        if regions_input:
            return [r.strip() for r in regions_input.split(",") if r.strip()]

    return []


def _configure_scanners() -> list[str]:
    """Configure which scanners to run."""
    scan_mode = questionary.select(
        "Scanner selection:",
        choices=[
            questionary.Choice("Run all scanners (recommended)", value="all"),
            questionary.Choice("Select specific scanners", value="select"),
        ],
    ).ask()

    if scan_mode == "select":
        choices = [
            questionary.Choice(
                f"{name} - {meta.description}",
                value=name,
                checked=True,
            )
            for name, meta in SCANNER_REGISTRY.items()
        ]
        selected = questionary.checkbox(
            "Select scanners to run:",
            choices=choices,
        ).ask()
        if selected:
            return selected

    return []


def _configure_options() -> dict:
    """Configure scan options."""
    max_workers = questionary.text(
        "Max parallel threads:",
        default="5",
        validate=lambda x: x.isdigit() and 1 <= int(x) <= 50 or "Must be 1-50",
    ).ask()

    output_dir = questionary.text(
        "Output directory:",
        default="./pinpoint-eda-output",
    ).ask()

    json_only = questionary.confirm(
        "JSON-only output (no Rich display)?",
        default=False,
    ).ask()

    return {
        "max_workers": int(max_workers) if max_workers else 5,
        "output_dir": Path(output_dir) if output_dir else Path("./pinpoint-eda-output"),
        "json_only": json_only or False,
    }


def _confirm_config(config: ScanConfig) -> bool:
    """Show config summary and ask for confirmation."""
    console.print()
    console.print("[bold]Scan Configuration Summary:[/]")
    console.print(f"  Accounts: {', '.join(a.label for a in config.accounts)}")
    regions_str = "auto-discover" if not config.regions else ", ".join(config.regions)
    console.print(f"  Regions: {regions_str}")
    console.print(f"  Scanners: {'all' if not config.scanners else ', '.join(config.scanners)}")
    console.print(f"  Max workers: {config.max_workers}")
    console.print(f"  Output: {config.output_dir}")
    console.print()

    return questionary.confirm("Start scan with these settings?", default=True).ask() or False
