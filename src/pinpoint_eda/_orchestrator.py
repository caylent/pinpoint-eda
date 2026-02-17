"""Central scan coordinator."""

from __future__ import annotations

import logging
import signal
import sys
import time

from rich.console import Console

from pinpoint_eda.aws_session import AWSSessionManager
from pinpoint_eda.checkpoint import CheckpointManager
from pinpoint_eda.config import AccountConfig, ScanConfig
from pinpoint_eda.exceptions import PinpointEDAError
from pinpoint_eda.executor import ScanExecutor
from pinpoint_eda.progress import ProgressDisplay
from pinpoint_eda.rate_limiter import RateLimiter
from pinpoint_eda.region_discovery import discover_regions
from pinpoint_eda.scanners import SCANNER_REGISTRY, get_active_scanners, get_scanner_class
from pinpoint_eda.scanners.base import ScanResult

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates the full scan lifecycle."""

    def __init__(self, config: ScanConfig, console: Console) -> None:
        self.config = config
        self.console = console
        self.session_manager = AWSSessionManager(config.accounts)
        self.rate_limiter = RateLimiter(requests_per_second=50.0)
        self.checkpoint = CheckpointManager(config.output_dir, config.config_hash())
        self.executor = ScanExecutor(max_workers=config.max_workers)
        self.progress = ProgressDisplay(console) if not config.json_only else None
        self._results: dict[str, list[ScanResult]] = {}
        self._account_ids: dict[str, str] = {}
        self._scan_start: float = 0
        self._ctrl_c_count = 0

        # Configure logging
        if config.verbose:
            logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")
        else:
            logging.basicConfig(level=logging.WARNING)

    def run(self) -> None:
        """Execute the full scan pipeline."""
        self._install_signal_handler()
        self._scan_start = time.monotonic()

        try:
            # Initialize checkpoint
            self.checkpoint.initialize(resume=self.config.resume)

            if self.progress:
                self.progress.start()

            # For each account, discover and scan
            for account in self.config.accounts:
                if self.executor.should_stop:
                    break
                self._scan_account(account)

            # Generate report
            scan_duration = time.monotonic() - self._scan_start
            self._generate_report(scan_duration)

            # Clean up checkpoint on successful completion
            if not self.executor.should_stop:
                self.checkpoint.cleanup()

        except PinpointEDAError as e:
            self.console.print(f"[bold red]Error:[/] {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Scan interrupted. Use --resume to continue.[/]")
        finally:
            if self.progress:
                self.progress.stop()

    def _scan_account(self, account: AccountConfig) -> None:
        """Scan all regions for a single account."""
        # Resolve real AWS account ID via STS
        account_id = self.session_manager.resolve_account_id(account)
        display_label = account_id
        if account.label != "default":
            display_label = f"{account_id} ({account.label})"

        if self.progress:
            self.progress.set_account_info(display_label)

        # Store resolved account ID for result keys
        self._account_ids[account.label] = account_id

        # Discover regions (or use specified regions)
        regions_with_apps = self._discover_regions(account)
        if not regions_with_apps:
            self.console.print(f"[yellow]No Pinpoint apps found for {display_label}[/]")
            return

        # Scan each region
        for region, app_ids in regions_with_apps.items():
            if self.executor.should_stop:
                break
            self._scan_region(account, region, app_ids)

    def _discover_regions(self, account: AccountConfig) -> dict[str, list[str]]:
        """Discover regions with Pinpoint apps, respecting checkpoint and --region."""
        # Check for resumed discovery
        if self.config.resume:
            cached = self.checkpoint.get_discovered_regions()
            if cached:
                logger.info("Using cached region discovery from checkpoint")
                return cached

        if self.config.regions:
            # User specified regions -- probe only those
            regions_with_apps = {}
            for region in self.config.regions:
                try:
                    client = self.session_manager.get_pinpoint_client(account, region)
                    response = client.get_apps(PageSize="100")
                    apps = response.get("ApplicationsResponse", {}).get("Item", [])
                    app_ids = [a["Id"] for a in apps]
                    if self.config.app_ids:
                        app_ids = [a for a in app_ids if a in self.config.app_ids]
                    if app_ids:
                        regions_with_apps[region] = app_ids
                except Exception as e:
                    logger.warning("Failed to probe %s: %s", region, e)
            self.checkpoint.set_discovered_regions(regions_with_apps)
            return regions_with_apps

        # Full auto-discovery
        regions_with_apps = discover_regions(
            self.session_manager, account, self.progress
        )

        # Filter to specific app IDs if provided
        if self.config.app_ids:
            for region in list(regions_with_apps):
                filtered = [a for a in regions_with_apps[region] if a in self.config.app_ids]
                if filtered:
                    regions_with_apps[region] = filtered
                else:
                    del regions_with_apps[region]

        self.checkpoint.set_discovered_regions(regions_with_apps)
        return regions_with_apps

    def _scan_region(
        self, account: AccountConfig, region: str, app_ids: list[str]
    ) -> None:
        """Scan all apps in a region using parallel threads."""
        active_scanners = get_active_scanners(
            selected=self.config.scanners or None,
            no_sms_voice_v2=self.config.no_sms_voice_v2,
        )

        # Separate per-app and account-level scanners
        per_app_scanners = [s for s in active_scanners if SCANNER_REGISTRY[s].per_app]
        account_scanners = [s for s in active_scanners if not SCANNER_REGISTRY[s].per_app]

        if self.progress:
            self.progress.add_region(region, len(app_ids))

        # Result key uses resolved account ID
        account_id = self._account_ids.get(account.label, account.label)
        result_key = f"{account_id}:{region}"

        # Run per-app scanners in parallel across apps
        def scan_app(app_id: str) -> list[ScanResult]:
            return self._scan_single_app(account, region, app_id, per_app_scanners)

        if per_app_scanners and app_ids:
            results = self.executor.map_parallel(scan_app, app_ids)
            for app_id, app_results, error in results:
                if error:
                    logger.error("Error scanning app %s: %s", app_id, error)
                    if self.progress:
                        self.progress.increment_errors()
                elif app_results:
                    self._results.setdefault(result_key, []).extend(app_results)

        # Run account-level scanners sequentially
        for scanner_name in account_scanners:
            if self.executor.should_stop:
                break
            ck_key = f"{scanner_name}:{region}:account"
            if self.checkpoint.is_completed(ck_key):
                continue

            try:
                self.checkpoint.mark_in_progress(ck_key)
                scanner_cls = get_scanner_class(scanner_name)

                if scanner_name == "sms_voice_v2":
                    client = self.session_manager.get_sms_voice_v2_client(account, region)
                else:
                    client = self.session_manager.get_pinpoint_client(account, region)

                scanner = scanner_cls(
                    client=client,
                    rate_limiter=self.rate_limiter,
                    region=region,
                    progress=self.progress,
                    kpi_days=self.config.kpi_days,
                )
                scan_result = scanner.scan()
                self.checkpoint.mark_completed(
                    ck_key, scan_result.resource_count, scan_result.to_dict()
                )
                self._results.setdefault(result_key, []).append(scan_result)
            except Exception as e:
                self.checkpoint.mark_error(ck_key, str(e))
                logger.error("Account scanner %s failed in %s: %s", scanner_name, region, e)
                if self.progress:
                    self.progress.increment_errors()

    def _scan_single_app(
        self,
        account: AccountConfig,
        region: str,
        app_id: str,
        scanner_names: list[str],
    ) -> list[ScanResult]:
        """Run all per-app scanners sequentially for one application."""
        client = self.session_manager.get_pinpoint_client(account, region)

        # Get app name for display
        app_name = app_id[:12]
        try:
            resp = self.rate_limiter.call_with_retry(
                client.get_app, ApplicationId=app_id
            )
            app_name = resp.get("ApplicationResponse", {}).get("Name", app_id[:12])
        except Exception:
            pass

        if self.progress:
            self.progress.add_app_task(region, app_name, len(scanner_names))

        results: list[ScanResult] = []

        for scanner_name in scanner_names:
            if self.executor.should_stop:
                break

            ck_key = f"{scanner_name}:{region}:{app_id}"
            if self.checkpoint.is_completed(ck_key):
                if self.progress:
                    self.progress.advance_app(region, app_name, scanner_name)
                continue

            try:
                self.checkpoint.mark_in_progress(ck_key)
                scanner_cls = get_scanner_class(scanner_name)
                scanner = scanner_cls(
                    client=client,
                    rate_limiter=self.rate_limiter,
                    region=region,
                    app_id=app_id,
                    progress=self.progress,
                    kpi_days=self.config.kpi_days,
                )
                scan_result = scanner.scan()
                self.checkpoint.mark_completed(
                    ck_key, scan_result.resource_count, scan_result.to_dict()
                )
                results.append(scan_result)
            except Exception as e:
                self.checkpoint.mark_error(ck_key, str(e))
                logger.error(
                    "Scanner %s failed for app %s in %s: %s",
                    scanner_name, app_id, region, e,
                )
                if self.progress:
                    self.progress.increment_errors()
            finally:
                if self.progress:
                    self.progress.advance_app(region, app_name, scanner_name)

            # Update throughput display
            if self.progress:
                self.progress.update_throughput(self.rate_limiter.throughput)

        return results

    def _generate_report(self, scan_duration: float) -> None:
        """Generate the final report."""
        from pinpoint_eda.complexity import assess_complexity
        from pinpoint_eda.report import generate_report

        # Merge checkpoint results with in-memory results
        all_results = dict(self._results)

        # Also load completed results from checkpoint (for resumed scans)
        checkpoint_results = self.checkpoint.get_scan_results()
        for ck_key, result_data in checkpoint_results.items():
            # Parse key: scanner_name:region:app_id
            parts = ck_key.split(":", 2)
            if len(parts) == 3:
                region_key = parts[1]
                # Find the account label for this region
                for acct_region_key in all_results:
                    if acct_region_key.endswith(f":{region_key}"):
                        break
                else:
                    acct_region_key = f"default:{region_key}"
                # Only add if not already present in memory
                existing_scanners = {
                    r.scanner_name for r in all_results.get(acct_region_key, [])
                    if isinstance(r, ScanResult) and r.app_id == parts[2]
                }
                if parts[0] not in existing_scanners:
                    scan_result = ScanResult(
                        scanner_name=result_data.get("scanner_name", parts[0]),
                        region=result_data.get("region", parts[1]),
                        app_id=result_data.get("app_id", parts[2]),
                        resource_count=result_data.get("resource_count", 0),
                        resources=result_data.get("resources", []),
                        metadata=result_data.get("metadata", {}),
                        errors=result_data.get("errors", []),
                    )
                    all_results.setdefault(acct_region_key, []).append(scan_result)

        # Assess complexity
        complexity = assess_complexity(all_results)

        # Generate report
        generate_report(
            results=all_results,
            complexity=complexity,
            config=self.config,
            scan_duration=scan_duration,
            api_calls=self.rate_limiter.total_calls,
            errors=self.checkpoint.errors,
            console=self.console,
            account_ids=self._account_ids,
        )

    def _install_signal_handler(self) -> None:
        """Install ctrl+c handler for graceful shutdown."""
        def handler(signum, frame):
            self._ctrl_c_count += 1
            if self._ctrl_c_count == 1:
                self.console.print(
                    "\n[yellow]Graceful shutdown requested. "
                    "Finishing current scanners... (ctrl+c again to force quit)[/]"
                )
                self.executor.request_shutdown()
            else:
                self.console.print("\n[red]Force quit.[/]")
                if self.progress:
                    self.progress.stop()
                sys.exit(1)

        signal.signal(signal.SIGINT, handler)
