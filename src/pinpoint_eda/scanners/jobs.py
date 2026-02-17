"""Scanner for Pinpoint import and export jobs."""

from __future__ import annotations

from pinpoint_eda.pagination import paginate_pinpoint
from pinpoint_eda.scanners.base import BaseScanner, ScanResult


class JobsScanner(BaseScanner):
    name = "jobs"
    description = "Import and export job history"
    per_app = True

    def scan(self) -> ScanResult:
        self._update_status(f"Scanning jobs for {self.app_id}")

        result = ScanResult(
            scanner_name=self.name,
            region=self.region,
            app_id=self.app_id,
        )

        import_jobs = []
        export_jobs = []

        try:
            import_jobs = paginate_pinpoint(
                api_method=self.client.get_import_jobs,
                rate_limiter=self.rate_limiter,
                response_key="ImportJobsResponse",
                items_key="Item",
                ApplicationId=self.app_id,
            )
        except Exception as e:
            result.errors.append(f"import_jobs: {e}")

        try:
            export_jobs = paginate_pinpoint(
                api_method=self.client.get_export_jobs,
                rate_limiter=self.rate_limiter,
                response_key="ExportJobsResponse",
                items_key="Item",
                ApplicationId=self.app_id,
            )
        except Exception as e:
            result.errors.append(f"export_jobs: {e}")

        # Classify job statuses
        import_statuses: dict[str, int] = {}
        for job in import_jobs:
            status = job.get("JobStatus", "UNKNOWN")
            import_statuses[status] = import_statuses.get(status, 0) + 1

        export_statuses: dict[str, int] = {}
        for job in export_jobs:
            status = job.get("JobStatus", "UNKNOWN")
            export_statuses[status] = export_statuses.get(status, 0) + 1

        result.resources = [
            {"type": "import", "jobs": import_jobs},
            {"type": "export", "jobs": export_jobs},
        ]
        result.resource_count = len(import_jobs) + len(export_jobs)
        result.metadata = {
            "import_count": len(import_jobs),
            "export_count": len(export_jobs),
            "import_statuses": import_statuses,
            "export_statuses": export_statuses,
        }

        self._increment_stat("Jobs", result.resource_count)
        return result
