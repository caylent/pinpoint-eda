"""Scanner for Pinpoint application metadata."""

from __future__ import annotations

from pinpoint_eda.scanners.base import BaseScanner, ScanResult


class ApplicationsScanner(BaseScanner):
    name = "applications"
    description = "Application metadata, ARN, tags"
    per_app = True

    def scan(self) -> ScanResult:
        self._update_status(f"Getting application details for {self.app_id}")

        result = ScanResult(
            scanner_name=self.name,
            region=self.region,
            app_id=self.app_id,
        )

        try:
            response = self.rate_limiter.call_with_retry(
                self.client.get_app,
                ApplicationId=self.app_id,
            )
            app = response.get("ApplicationResponse", {})
            result.resources = [app]
            result.resource_count = 1
            result.metadata = {
                "name": app.get("Name", ""),
                "arn": app.get("Arn", ""),
                "creation_date": app.get("CreationDate", ""),
            }

            # Try to get tags
            try:
                tags_response = self.rate_limiter.call_with_retry(
                    self.client.list_tags_for_resource,
                    ResourceArn=app.get("Arn", ""),
                )
                result.metadata["tags"] = tags_response.get("TagsModel", {}).get("tags", {})
            except Exception:
                result.metadata["tags"] = {}

            self._increment_stat("Applications", 1)
        except Exception as e:
            result.errors.append(str(e))

        return result
