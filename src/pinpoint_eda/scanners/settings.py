"""Scanner for Pinpoint application settings."""

from __future__ import annotations

from pinpoint_eda.scanners.base import BaseScanner, ScanResult


class SettingsScanner(BaseScanner):
    name = "settings"
    description = "Application settings and limits"
    per_app = True

    def scan(self) -> ScanResult:
        self._update_status(f"Getting settings for {self.app_id}")

        result = ScanResult(
            scanner_name=self.name,
            region=self.region,
            app_id=self.app_id,
        )

        try:
            response = self.rate_limiter.call_with_retry(
                self.client.get_application_settings,
                ApplicationId=self.app_id,
            )
            settings = response.get("ApplicationSettingsResource", {})
            result.resources = [settings]
            result.resource_count = 1
            result.metadata = {
                "quiet_time": settings.get("QuietTime"),
                "limits": settings.get("Limits"),
                "campaign_hook": settings.get("CampaignHook"),
            }
        except Exception as e:
            result.errors.append(str(e))

        return result
