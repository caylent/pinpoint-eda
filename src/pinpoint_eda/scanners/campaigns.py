"""Scanner for Pinpoint campaigns."""

from __future__ import annotations

from pinpoint_eda.pagination import paginate_pinpoint
from pinpoint_eda.scanners.base import BaseScanner, ScanResult


class CampaignsScanner(BaseScanner):
    name = "campaigns"
    description = "Campaigns with versions and state breakdown"
    per_app = True

    def scan(self) -> ScanResult:
        self._update_status(f"Scanning campaigns for {self.app_id}")

        result = ScanResult(
            scanner_name=self.name,
            region=self.region,
            app_id=self.app_id,
        )

        try:
            campaigns = paginate_pinpoint(
                api_method=self.client.get_campaigns,
                rate_limiter=self.rate_limiter,
                response_key="CampaignsResponse",
                items_key="Item",
                ApplicationId=self.app_id,
            )

            # Classify campaigns by state
            state_counts: dict[str, int] = {}
            for campaign in campaigns:
                state = campaign.get("State", {}).get("CampaignStatus", "UNKNOWN")
                state_counts[state] = state_counts.get(state, 0) + 1

                # Get version count
                try:
                    versions = paginate_pinpoint(
                        api_method=self.client.get_campaign_versions,
                        rate_limiter=self.rate_limiter,
                        response_key="CampaignsResponse",
                        items_key="Item",
                        ApplicationId=self.app_id,
                        CampaignId=campaign["Id"],
                    )
                    campaign["_version_count"] = len(versions)
                except Exception:
                    campaign["_version_count"] = 0

            result.resources = campaigns
            result.resource_count = len(campaigns)
            result.metadata = {
                "total": len(campaigns),
                "state_breakdown": state_counts,
                "active": (
                    state_counts.get("EXECUTING", 0) + state_counts.get("PENDING_NEXT_RUN", 0)
                ),
            }

            self._increment_stat("Campaigns", len(campaigns))
        except Exception as e:
            result.errors.append(str(e))

        return result
