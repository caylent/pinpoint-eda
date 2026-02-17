"""Migration complexity scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pinpoint_eda.scanners.base import ScanResult


class ComplexityLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


COMPLEXITY_THRESHOLDS = {
    ComplexityLevel.LOW: (0, 10),
    ComplexityLevel.MEDIUM: (10, 30),
    ComplexityLevel.HIGH: (30, 70),
    ComplexityLevel.VERY_HIGH: (70, float("inf")),
}

# Migration target mapping
MIGRATION_TARGETS: dict[str, dict[str, str]] = {
    "campaigns": {
        "target": "Amazon Connect Outbound Campaigns",
        "notes": "Outbound voice/SMS campaigns via Connect. Email campaigns via SES.",
    },
    "journeys": {
        "target": "Amazon Connect Customer Profiles + Step Functions",
        "notes": "No direct equivalent. Journeys must be decomposed into workflow steps.",
    },
    "segments": {
        "target": "Amazon Connect Customer Profiles / Amazon SES",
        "notes": "Dynamic segments need re-implementation. Imported segments can be migrated.",
    },
    "templates": {
        "target": "Amazon SES Templates / Amazon Connect",
        "notes": "Email/SMS templates to SES. Push templates have no equivalent.",
    },
    "channels_email": {
        "target": "Amazon SES",
        "notes": "Direct migration path. SES is already the underlying provider.",
    },
    "channels_sms": {
        "target": "Amazon Connect SMS / Amazon SNS",
        "notes": "SMS via Connect or SNS depending on use case.",
    },
    "channels_push": {
        "target": "Amazon SNS",
        "notes": "Push notifications via SNS. Campaign-linked push is more complex.",
    },
    "channels_voice": {
        "target": "Amazon Connect",
        "notes": "Voice messaging via Amazon Connect.",
    },
    "event_streams": {
        "target": "Amazon Kinesis / Amazon EventBridge",
        "notes": "Event streaming continues via Kinesis. May need EventBridge for routing.",
    },
    "recommenders": {
        "target": "Amazon Personalize",
        "notes": "Custom ML recommender integrations need re-wiring.",
    },
    "kpis": {
        "target": "Amazon Connect Analytics / CloudWatch",
        "notes": "Analytics via Connect dashboards and CloudWatch metrics.",
    },
    "inapp_templates": {
        "target": "No AWS equivalent",
        "notes": (
            "In-app messaging templates have no direct AWS replacement. "
            "Consider third-party."
        ),
    },
    "sms_voice_v2": {
        "target": "Amazon Connect SMS/Voice",
        "notes": "Phone numbers, pools, and registrations managed via Connect.",
    },
}


@dataclass
class ComplexityFactor:
    """A single factor contributing to complexity score."""

    name: str
    score: int
    explanation: str
    migration_target: str = ""


@dataclass
class AppComplexity:
    """Complexity assessment for a single application."""

    app_id: str
    app_name: str
    region: str
    total_score: int = 0
    level: ComplexityLevel = ComplexityLevel.LOW
    factors: list[ComplexityFactor] = field(default_factory=list)
    is_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "app_name": self.app_name,
            "region": self.region,
            "total_score": self.total_score,
            "level": self.level.value,
            "is_active": self.is_active,
            "factors": [
                {
                    "name": f.name,
                    "score": f.score,
                    "explanation": f.explanation,
                    "migration_target": f.migration_target,
                }
                for f in self.factors
            ],
        }


@dataclass
class AccountComplexity:
    """Complexity for account-level resources in a region."""

    region: str
    total_score: int = 0
    factors: list[ComplexityFactor] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "total_score": self.total_score,
            "factors": [
                {
                    "name": f.name,
                    "score": f.score,
                    "explanation": f.explanation,
                    "migration_target": f.migration_target,
                }
                for f in self.factors
            ],
        }


@dataclass
class ComplexityAssessment:
    """Overall complexity assessment across all apps."""

    overall_score: int = 0
    overall_level: ComplexityLevel = ComplexityLevel.LOW
    app_assessments: list[AppComplexity] = field(default_factory=list)
    account_assessments: list[AccountComplexity] = field(default_factory=list)
    migration_targets: dict[str, dict[str, str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "overall_level": self.overall_level.value,
            "app_assessments": [a.to_dict() for a in self.app_assessments],
            "account_assessments": [a.to_dict() for a in self.account_assessments],
            "migration_targets": self.migration_targets,
        }


def _score_to_level(score: int) -> ComplexityLevel:
    """Convert a numeric score to a complexity level."""
    for level, (low, high) in COMPLEXITY_THRESHOLDS.items():
        if low <= score < high:
            return level
    return ComplexityLevel.VERY_HIGH


def _score_journey(jc: dict) -> tuple[int, str]:
    """Score a single journey based on its state and activity complexity.

    Returns (score, explanation).
    """
    state = jc.get("state", "UNKNOWN")
    activity_count = jc.get("activity_count", 0)
    branching_count = jc.get("branching_count", 0)
    integration_count = jc.get("integration_count", 0)
    name = jc.get("name", jc.get("id", "?"))

    # Base score by state
    if state == "DRAFT":
        base = 1
    elif state == "ACTIVE":
        base = 5
    elif state in ("PAUSED", "CANCELLED"):
        base = 2
    elif state in ("COMPLETED", "CLOSED"):
        base = 3
    else:
        base = 2

    # Activity count adds complexity (each activity is a step to rebuild)
    activity_score = 0
    if activity_count <= 3:
        activity_score = 1
    elif activity_count <= 10:
        activity_score = 3
    else:
        activity_score = 5

    # Branching adds significant complexity (conditional logic to recreate)
    branching_score = branching_count * 2

    # External integrations (ContactCenter, Custom) are hardest to migrate
    integration_score = integration_count * 3

    total = base + activity_score + branching_score + integration_score

    parts = [f'"{name}" ({state.lower()}, {activity_count} activities']
    if branching_count:
        parts[0] += f", {branching_count} branches"
    if integration_count:
        parts[0] += f", {integration_count} integrations"
    parts[0] += ")"

    return total, parts[0]


def _assess_account_resources(
    region: str,
    results: list[ScanResult],
) -> AccountComplexity:
    """Score account-level resources (templates, recommenders, sms_voice_v2)."""
    factors: list[ComplexityFactor] = []

    by_scanner = {r.scanner_name: r for r in results if r.app_id == "account"}

    # Templates: 1 pt each, in-app = 8 pts each
    templates_result = by_scanner.get("templates")
    if templates_result and templates_result.resource_count > 0:
        total = templates_result.resource_count
        type_breakdown = templates_result.metadata.get("type_breakdown", {})
        inapp_count = type_breakdown.get("INAPP", 0)
        score = (total - inapp_count) * 1 + inapp_count * 8
        explanation = f"{total} templates"
        if inapp_count:
            explanation += f" ({inapp_count} in-app -- no AWS equivalent)"
        factors.append(ComplexityFactor(
            name="Templates",
            score=score,
            explanation=explanation + ".",
            migration_target=MIGRATION_TARGETS["templates"]["target"],
        ))

    # Recommenders: 5 pts each
    recommenders_result = by_scanner.get("recommenders")
    if recommenders_result and recommenders_result.resource_count > 0:
        count = recommenders_result.resource_count
        factors.append(ComplexityFactor(
            name="Recommenders",
            score=count * 5,
            explanation=f"{count} ML recommender integrations.",
            migration_target=MIGRATION_TARGETS["recommenders"]["target"],
        ))

    # SMS Voice V2 resources (scored once per region, not per app)
    sms_result = by_scanner.get("sms_voice_v2")
    if sms_result and sms_result.resource_count > 0:
        phone_count = sms_result.metadata.get("phone_numbers", 0)
        pool_count = sms_result.metadata.get("pools", 0)
        reg_count = sms_result.metadata.get("registrations", 0)
        config_sets = sms_result.metadata.get("configuration_sets", 0)
        score = phone_count * 2 + pool_count * 2 + reg_count * 3 + config_sets
        if score > 0:
            parts = []
            if phone_count:
                parts.append(f"{phone_count} phone numbers")
            if pool_count:
                parts.append(f"{pool_count} pools")
            if reg_count:
                parts.append(f"{reg_count} registrations")
            if config_sets:
                parts.append(f"{config_sets} config sets")
            factors.append(ComplexityFactor(
                name="SMS/Voice V2",
                score=score,
                explanation=", ".join(parts) + ".",
                migration_target=MIGRATION_TARGETS["sms_voice_v2"]["target"],
            ))

    total_score = sum(f.score for f in factors)
    return AccountComplexity(
        region=region,
        total_score=total_score,
        factors=sorted(factors, key=lambda f: f.score, reverse=True),
    )


def _assess_app(
    app_id: str,
    region: str,
    results: list[ScanResult],
) -> AppComplexity:
    """Score a single application's migration complexity (per-app resources only)."""
    app_name = app_id
    factors: list[ComplexityFactor] = []

    # Only per-app results (exclude account-level)
    by_scanner: dict[str, ScanResult] = {}
    for r in results:
        if r.app_id == app_id:
            by_scanner[r.scanner_name] = r

    # Get app name
    app_result = by_scanner.get("applications")
    if app_result and app_result.metadata:
        app_name = app_result.metadata.get("name", app_id)

    # Determine if app is actively used (from KPI data)
    is_active = False
    kpis_result = by_scanner.get("kpis")
    if kpis_result and kpis_result.metadata:
        is_active = kpis_result.metadata.get("is_active", False)

    # Campaign hook / Lambda integration
    settings_result = by_scanner.get("settings")
    if settings_result and settings_result.metadata:
        hook = settings_result.metadata.get("campaign_hook")
        if hook and hook.get("LambdaFunctionName"):
            factors.append(ComplexityFactor(
                name="Campaign Hook",
                score=5,
                explanation=(
                    f"Lambda hook: {hook['LambdaFunctionName']}. "
                    "Custom integration needs re-wiring."
                ),
                migration_target="AWS Lambda + Amazon Connect",
            ))

    # Journeys -- scored per journey based on complexity
    journeys_result = by_scanner.get("journeys")
    if journeys_result and journeys_result.resource_count > 0:
        journey_complexities = journeys_result.metadata.get(
            "journey_complexities", []
        )
        total_journey_score = 0
        journey_explanations = []

        for jc in journey_complexities:
            score, explanation = _score_journey(jc)
            total_journey_score += score
            journey_explanations.append(f"  {explanation}: {score}pts")

        if total_journey_score > 0:
            count = journeys_result.resource_count
            active = journeys_result.metadata.get("active", 0)
            summary = (
                f"{count} journeys ({active} active). "
                "No direct Connect equivalent.\n"
            )
            summary += "\n".join(journey_explanations)
            factors.append(ComplexityFactor(
                name="Journeys",
                score=total_journey_score,
                explanation=summary,
                migration_target=MIGRATION_TARGETS["journeys"]["target"],
            ))

    # Campaigns: active=3, inactive=1
    campaigns_result = by_scanner.get("campaigns")
    if campaigns_result and campaigns_result.resource_count > 0:
        total = campaigns_result.resource_count
        active = campaigns_result.metadata.get("active", 0)
        score = active * 3 + (total - active) * 1
        if score > 0:
            factors.append(ComplexityFactor(
                name="Campaigns",
                score=score,
                explanation=(
                    f"{total} campaigns ({active} active). "
                    "Active need careful cutover."
                ),
                migration_target=MIGRATION_TARGETS["campaigns"]["target"],
            ))

    # Segments: 1 pt each, dynamic +3, imported +2
    segments_result = by_scanner.get("segments")
    if segments_result and segments_result.resource_count > 0:
        total = segments_result.resource_count
        dynamic = segments_result.metadata.get("dynamic", 0)
        imported = segments_result.metadata.get("imported", 0)
        score = total + (dynamic * 3) + (imported * 2)
        factors.append(ComplexityFactor(
            name="Segments",
            score=score,
            explanation=(
                f"{total} segments ({dynamic} dynamic, {imported} imported)."
            ),
            migration_target=MIGRATION_TARGETS["segments"]["target"],
        ))

    # Channels: 2 pts each active
    channels_result = by_scanner.get("channels")
    if channels_result:
        active_channels = channels_result.metadata.get("active_channels", [])
        if active_channels:
            push_types = {
                "APNS", "APNSSandbox", "APNSVoip", "GCM", "Baidu", "ADM",
            }
            has_push = bool(push_types & set(active_channels))
            has_active_campaigns = bool(
                campaigns_result
                and campaigns_result.metadata.get("active", 0)
            )
            if has_push and has_active_campaigns:
                factors.append(ComplexityFactor(
                    name="Push + Campaigns",
                    score=5,
                    explanation=(
                        "Push channels with active campaigns. "
                        "Not supported in Connect outbound."
                    ),
                    migration_target=MIGRATION_TARGETS["channels_push"]["target"],
                ))

            channel_names = ", ".join(active_channels)
            factors.append(ComplexityFactor(
                name="Active Channels",
                score=len(active_channels) * 2,
                explanation=f"{len(active_channels)} active: {channel_names}.",
                migration_target="Various (SES, SNS, Connect)",
            ))

    # Event streams: 3 pts, more if app has active deliveries
    event_result = by_scanner.get("event_streams")
    if event_result and event_result.metadata.get("has_event_stream"):
        score = 5 if is_active else 3
        explanation = "Event stream configured."
        if is_active:
            explanation += " App has recent activity -- downstream consumers likely active."
        else:
            explanation += " Need to maintain event pipeline."
        factors.append(ComplexityFactor(
            name="Event Stream",
            score=score,
            explanation=explanation,
            migration_target=MIGRATION_TARGETS["event_streams"]["target"],
        ))

    # Import jobs as signal of external data pipelines
    jobs_result = by_scanner.get("jobs")
    if jobs_result:
        import_count = jobs_result.metadata.get("import_count", 0)
        if import_count > 0:
            factors.append(ComplexityFactor(
                name="Import Jobs",
                score=2,
                explanation=(
                    f"{import_count} historical import jobs. "
                    "External data pipeline may need redirecting."
                ),
                migration_target="Amazon Connect Customer Profiles",
            ))

    total_score = sum(f.score for f in factors)
    return AppComplexity(
        app_id=app_id,
        app_name=app_name,
        region=region,
        total_score=total_score,
        level=_score_to_level(total_score),
        factors=sorted(factors, key=lambda f: f.score, reverse=True),
        is_active=is_active,
    )


def assess_complexity(
    results: dict[str, list[ScanResult]],
) -> ComplexityAssessment:
    """Assess migration complexity across all scanned applications."""
    app_assessments: list[AppComplexity] = []
    account_assessments: list[AccountComplexity] = []

    for region_key, scan_results in results.items():
        # Group results by app_id
        apps: dict[str, list[ScanResult]] = {}
        for r in scan_results:
            apps.setdefault(r.app_id, []).append(r)

        # Parse region from key
        parts = region_key.split(":", 1)
        region = parts[1] if len(parts) > 1 else region_key

        # Score account-level resources once per region
        account_results = apps.get("account", [])
        if account_results:
            acct_assessment = _assess_account_resources(region, scan_results)
            if acct_assessment.total_score > 0:
                account_assessments.append(acct_assessment)

        # Score each app (per-app resources only)
        for app_id, app_results in apps.items():
            if app_id == "account":
                continue
            assessment = _assess_app(app_id, region, scan_results)
            app_assessments.append(assessment)

    app_total = sum(a.total_score for a in app_assessments)
    acct_total = sum(a.total_score for a in account_assessments)
    overall_score = app_total + acct_total

    return ComplexityAssessment(
        overall_score=overall_score,
        overall_level=_score_to_level(overall_score),
        app_assessments=sorted(
            app_assessments, key=lambda a: a.total_score, reverse=True
        ),
        account_assessments=account_assessments,
        migration_targets=MIGRATION_TARGETS,
    )
