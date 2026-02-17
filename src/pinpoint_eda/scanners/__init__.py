"""Scanner registry and metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pinpoint_eda.scanners.base import BaseScanner


@dataclass
class ScannerMeta:
    """Metadata about a scanner."""

    description: str
    per_app: bool
    scanner_class: str  # Dotted path for lazy loading
    module: str


SCANNER_REGISTRY: dict[str, ScannerMeta] = {
    "applications": ScannerMeta(
        description="Application metadata, ARN, tags",
        per_app=True,
        scanner_class="ApplicationsScanner",
        module="pinpoint_eda.scanners.applications",
    ),
    "settings": ScannerMeta(
        description="Application settings and limits",
        per_app=True,
        scanner_class="SettingsScanner",
        module="pinpoint_eda.scanners.settings",
    ),
    "channels": ScannerMeta(
        description="All 9 channel types (Email, SMS, Voice, APNS, GCM, etc.)",
        per_app=True,
        scanner_class="ChannelsScanner",
        module="pinpoint_eda.scanners.channels",
    ),
    "segments": ScannerMeta(
        description="Segments with version counts and type breakdown",
        per_app=True,
        scanner_class="SegmentsScanner",
        module="pinpoint_eda.scanners.segments",
    ),
    "campaigns": ScannerMeta(
        description="Campaigns with versions and state breakdown",
        per_app=True,
        scanner_class="CampaignsScanner",
        module="pinpoint_eda.scanners.campaigns",
    ),
    "journeys": ScannerMeta(
        description="Journeys with activities and execution metrics",
        per_app=True,
        scanner_class="JourneysScanner",
        module="pinpoint_eda.scanners.journeys",
    ),
    "templates": ScannerMeta(
        description="Email, SMS, Push, In-App, Voice templates",
        per_app=False,
        scanner_class="TemplatesScanner",
        module="pinpoint_eda.scanners.templates",
    ),
    "event_streams": ScannerMeta(
        description="Kinesis event stream configuration",
        per_app=True,
        scanner_class="EventStreamsScanner",
        module="pinpoint_eda.scanners.event_streams",
    ),
    "jobs": ScannerMeta(
        description="Import and export job history",
        per_app=True,
        scanner_class="JobsScanner",
        module="pinpoint_eda.scanners.jobs",
    ),
    "kpis": ScannerMeta(
        description="Application, campaign, and journey KPIs",
        per_app=True,
        scanner_class="KPIsScanner",
        module="pinpoint_eda.scanners.kpis",
    ),
    "recommenders": ScannerMeta(
        description="ML recommender configurations",
        per_app=False,
        scanner_class="RecommendersScanner",
        module="pinpoint_eda.scanners.recommenders",
    ),
    "sms_voice_v2": ScannerMeta(
        description="Phone numbers, pools, sender IDs, opt-out lists, registrations",
        per_app=False,
        scanner_class="SMSVoiceV2Scanner",
        module="pinpoint_eda.scanners.sms_voice_v2",
    ),
}

# Default scan order -- dependencies go first
SCANNER_ORDER = [
    "applications",
    "settings",
    "channels",
    "segments",
    "campaigns",
    "journeys",
    "templates",
    "event_streams",
    "jobs",
    "kpis",
    "recommenders",
    "sms_voice_v2",
]


def get_scanner_class(name: str) -> type[BaseScanner]:
    """Lazily import and return the scanner class by name."""
    import importlib

    meta = SCANNER_REGISTRY[name]
    module = importlib.import_module(meta.module)
    return getattr(module, meta.scanner_class)


def get_active_scanners(
    selected: list[str] | None = None,
    no_sms_voice_v2: bool = False,
) -> list[str]:
    """Return ordered list of active scanner names."""
    if selected:
        # Validate selected scanners
        for s in selected:
            if s not in SCANNER_REGISTRY:
                raise ValueError(f"Unknown scanner: {s}. Available: {list(SCANNER_REGISTRY)}")
        # Preserve SCANNER_ORDER for those selected
        return [s for s in SCANNER_ORDER if s in selected]

    scanners = list(SCANNER_ORDER)
    if no_sms_voice_v2:
        scanners = [s for s in scanners if s != "sms_voice_v2"]
    return scanners
