"""Rich Live display for hierarchical scan progress."""

from __future__ import annotations

import threading
from datetime import date

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text

PINPOINT_EOL = date(2026, 10, 30)


class ScanStats:
    """Thread-safe running totals for scan statistics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {}

    def increment(self, name: str, count: int = 1) -> None:
        with self._lock:
            self._counts[name] = self._counts.get(name, 0) + count

    def get(self, name: str) -> int:
        with self._lock:
            return self._counts.get(name, 0)

    def items(self) -> list[tuple[str, int]]:
        with self._lock:
            return list(self._counts.items())


class ProgressDisplay:
    """Manages the Rich Live terminal display."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self._region_progress: dict[str, Progress] = {}
        self._app_tasks: dict[str, TaskID] = {}
        self._stats = ScanStats()
        self._status_message = ""
        self._throughput = 0.0
        self._error_count = 0
        self._account_label = ""
        self._region_count = 0
        self._app_count = 0
        self._lock = threading.Lock()
        self._live: Live | None = None

        # Region discovery progress (separate)
        self._discovery_progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Region Discovery"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        )
        self._discovery_task: TaskID | None = None

    def _build_header(self) -> Panel:
        """Build the header panel with account info and EOL countdown."""
        days_remaining = (PINPOINT_EOL - date.today()).days
        if days_remaining > 180:
            eol_style = "green"
        elif days_remaining > 90:
            eol_style = "yellow"
        else:
            eol_style = "bold red"

        header_text = Text()
        header_text.append(f"  Account: {self._account_label}", style="bold")
        header_text.append(f" | Regions: {self._region_count} found")
        header_text.append(f" | Apps: {self._app_count} total\n")
        header_text.append("  Pinpoint EOL: Oct 30, 2026 (", style="dim")
        header_text.append(f"{days_remaining} days remaining", style=eol_style)
        header_text.append(")", style="dim")

        return Panel(header_text, title="Pinpoint EDA - Migration Assessment", border_style="blue")

    def _build_stats_line(self) -> Text:
        """Build the running stats line."""
        parts = []
        for name, count in self._stats.items():
            parts.append(f"{name}: {count}")
        if not parts:
            return Text("")
        return Text("  " + " | ".join(parts), style="dim")

    def _build_footer(self) -> Text:
        """Build the footer with status, throughput, errors."""
        footer = Text()
        if self._status_message:
            footer.append(f"  Current: {self._status_message}\n", style="dim")
        footer.append(f"  Throughput: {self._throughput:.0f} API calls/sec", style="dim")
        footer.append(f" | Errors: {self._error_count}", style="dim")
        return footer

    def _build_layout(self) -> RenderableType:
        """Compose the full display."""
        parts: list[RenderableType] = [self._build_header()]

        if self._discovery_task is not None:
            parts.append(self._discovery_progress)
            parts.append(Text(""))

        for region, progress in self._region_progress.items():
            parts.append(Text(f"  {region}:", style="bold cyan"))
            parts.append(progress)
            parts.append(Text(""))

        stats_line = self._build_stats_line()
        if stats_line.plain:
            parts.append(stats_line)

        parts.append(self._build_footer())
        return Group(*parts)

    def start(self) -> None:
        """Start the live display."""
        self._live = Live(
            self._build_layout(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
        )
        self._live.start()

    def stop(self) -> None:
        """Stop the live display."""
        if self._live:
            self._live.stop()
            self._live = None

    def _refresh(self) -> None:
        """Refresh the live display."""
        if self._live:
            self._live.update(self._build_layout())

    def set_account_info(self, label: str) -> None:
        with self._lock:
            self._account_label = label
            self._refresh()

    def start_discovery(self, total_regions: int) -> None:
        """Start the region discovery progress bar."""
        self._discovery_task = self._discovery_progress.add_task(
            "Discovering", total=total_regions
        )
        self._refresh()

    def advance_discovery(self) -> None:
        """Advance region discovery by one."""
        if self._discovery_task is not None:
            self._discovery_progress.advance(self._discovery_task)
            self._refresh()

    def finish_discovery(self, region_count: int, app_count: int) -> None:
        """Mark discovery complete and update counts."""
        with self._lock:
            self._region_count = region_count
            self._app_count = app_count
            self._refresh()

    def add_region(self, region: str, app_count: int) -> None:
        """Add a region progress section."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("    App: {task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
        )
        with self._lock:
            self._region_progress[region] = progress
            self._refresh()

    def add_app_task(self, region: str, app_name: str, total_scanners: int) -> None:
        """Add a progress bar for an application within a region."""
        key = f"{region}:{app_name}"
        with self._lock:
            progress = self._region_progress.get(region)
            if progress:
                task_id = progress.add_task(app_name, total=total_scanners)
                self._app_tasks[key] = task_id
                self._refresh()

    def advance_app(self, region: str, app_name: str, scanner_name: str) -> None:
        """Advance an app's progress bar by one scanner."""
        key = f"{region}:{app_name}"
        with self._lock:
            progress = self._region_progress.get(region)
            task_id = self._app_tasks.get(key)
            if progress and task_id is not None:
                progress.advance(task_id)
                self._refresh()

    def update_status(self, message: str) -> None:
        with self._lock:
            self._status_message = message
            self._refresh()

    def update_throughput(self, calls_per_sec: float) -> None:
        with self._lock:
            self._throughput = calls_per_sec
            self._refresh()

    def increment_stat(self, stat_name: str, count: int = 1) -> None:
        self._stats.increment(stat_name, count)
        self._refresh()

    def increment_errors(self) -> None:
        with self._lock:
            self._error_count += 1
            self._refresh()
