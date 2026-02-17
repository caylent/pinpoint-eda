"""Scanner for Pinpoint journeys."""

from __future__ import annotations

from pinpoint_eda.pagination import paginate_list
from pinpoint_eda.scanners.base import BaseScanner, ScanResult

# Activity types that add branching complexity
BRANCHING_ACTIVITIES = {"ConditionalSplit", "MultiCondition", "RandomSplit"}
# Activity types that involve external integrations
INTEGRATION_ACTIVITIES = {"ContactCenter", "Custom"}


class JourneysScanner(BaseScanner):
    name = "journeys"
    description = "Journeys with activities and execution metrics"
    per_app = True

    def scan(self) -> ScanResult:
        self._update_status(f"Scanning journeys for {self.app_id}")

        result = ScanResult(
            scanner_name=self.name,
            region=self.region,
            app_id=self.app_id,
        )

        try:
            journeys = paginate_list(
                api_method=self.client.list_journeys,
                rate_limiter=self.rate_limiter,
                response_key="JourneysResponse",
                items_key="Item",
                ApplicationId=self.app_id,
            )

            state_counts: dict[str, int] = {}
            total_activities = 0
            journey_complexities: list[dict] = []

            for journey_summary in journeys:
                journey_id = journey_summary.get("Id", "")
                state = journey_summary.get("State", "UNKNOWN")
                state_counts[state] = state_counts.get(state, 0) + 1

                jc: dict = {
                    "id": journey_id,
                    "name": journey_summary.get("Name", ""),
                    "state": state,
                    "activity_count": 0,
                    "branching_count": 0,
                    "integration_count": 0,
                    "activity_types": [],
                    "has_contact_center": False,
                    "has_custom_activity": False,
                }

                try:
                    detail_resp = self.rate_limiter.call_with_retry(
                        self.client.get_journey,
                        ApplicationId=self.app_id,
                        JourneyId=journey_id,
                    )
                    journey_detail = detail_resp.get("JourneyResponse", {})
                    activities = journey_detail.get("Activities", {})
                    activity_count = len(activities)
                    total_activities += activity_count

                    activity_types_set: set[str] = set()
                    branching_count = 0
                    integration_count = 0

                    for activity in activities.values():
                        atype = self._classify_activity(activity)
                        activity_types_set.add(atype)
                        if atype in BRANCHING_ACTIVITIES:
                            branching_count += 1
                        if atype in INTEGRATION_ACTIVITIES:
                            integration_count += 1

                    jc["activity_count"] = activity_count
                    jc["branching_count"] = branching_count
                    jc["integration_count"] = integration_count
                    jc["activity_types"] = sorted(activity_types_set)
                    jc["has_contact_center"] = "ContactCenter" in activity_types_set
                    jc["has_custom_activity"] = "Custom" in activity_types_set

                    journey_summary["_detail"] = {
                        "activity_count": activity_count,
                        "activity_types": sorted(activity_types_set),
                        "branching_count": branching_count,
                        "integration_count": integration_count,
                        "start_condition": journey_detail.get("StartCondition"),
                        "schedule": journey_detail.get("Schedule"),
                        "refresh_frequency": journey_detail.get(
                            "RefreshFrequency"
                        ),
                    }
                except Exception as e:
                    journey_summary["_detail"] = {"error": str(e)}

                # Get execution metrics if journey has been active
                if state in ("ACTIVE", "COMPLETED", "CLOSED"):
                    try:
                        metrics_resp = self.rate_limiter.call_with_retry(
                            self.client.get_journey_execution_metrics,
                            ApplicationId=self.app_id,
                            JourneyId=journey_id,
                        )
                        journey_summary["_execution_metrics"] = metrics_resp.get(
                            "JourneyExecutionMetricsResponse", {}
                        )
                    except Exception:
                        pass

                journey_complexities.append(jc)

            result.resources = journeys
            result.resource_count = len(journeys)
            result.metadata = {
                "total": len(journeys),
                "state_breakdown": state_counts,
                "active": state_counts.get("ACTIVE", 0),
                "total_activities": total_activities,
                "journey_complexities": journey_complexities,
            }

            self._increment_stat("Journeys", len(journeys))
        except Exception as e:
            result.errors.append(str(e))

        return result

    @staticmethod
    def _classify_activity(activity: dict) -> str:
        """Determine the type of a journey activity."""
        activity_types = [
            "ConditionalSplit", "Email", "Holdout", "MultiCondition",
            "Push", "RandomSplit", "SMS", "Wait", "ContactCenter",
            "Custom", "Voice",
        ]
        for at in activity_types:
            if at in activity:
                return at
        return "Unknown"
