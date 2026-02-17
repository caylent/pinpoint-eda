"""Scanner for Pinpoint segments."""

from __future__ import annotations

from pinpoint_eda.pagination import paginate_pinpoint
from pinpoint_eda.scanners.base import BaseScanner, ScanResult


class SegmentsScanner(BaseScanner):
    name = "segments"
    description = "Segments with version counts and type breakdown"
    per_app = True

    def scan(self) -> ScanResult:
        self._update_status(f"Scanning segments for {self.app_id}")

        result = ScanResult(
            scanner_name=self.name,
            region=self.region,
            app_id=self.app_id,
        )

        try:
            segments = paginate_pinpoint(
                api_method=self.client.get_segments,
                rate_limiter=self.rate_limiter,
                response_key="SegmentsResponse",
                items_key="Item",
                ApplicationId=self.app_id,
            )

            # Classify segments
            dynamic_count = 0
            imported_count = 0
            for seg in segments:
                seg_type = seg.get("SegmentType", "")
                if seg_type == "DIMENSIONAL":
                    dynamic_count += 1
                elif seg_type == "IMPORT":
                    imported_count += 1

                # Get version count for each segment
                try:
                    versions = paginate_pinpoint(
                        api_method=self.client.get_segment_versions,
                        rate_limiter=self.rate_limiter,
                        response_key="SegmentsResponse",
                        items_key="Item",
                        ApplicationId=self.app_id,
                        SegmentId=seg["Id"],
                    )
                    seg["_version_count"] = len(versions)
                except Exception:
                    seg["_version_count"] = 0

            result.resources = segments
            result.resource_count = len(segments)
            result.metadata = {
                "total": len(segments),
                "dynamic": dynamic_count,
                "imported": imported_count,
            }

            self._increment_stat("Segments", len(segments))
        except Exception as e:
            result.errors.append(str(e))

        return result
