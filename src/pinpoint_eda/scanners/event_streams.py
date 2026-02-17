"""Scanner for Pinpoint event streams."""

from __future__ import annotations

from pinpoint_eda.scanners.base import BaseScanner, ScanResult


class EventStreamsScanner(BaseScanner):
    name = "event_streams"
    description = "Kinesis event stream configuration"
    per_app = True

    def scan(self) -> ScanResult:
        self._update_status(f"Checking event stream for {self.app_id}")

        result = ScanResult(
            scanner_name=self.name,
            region=self.region,
            app_id=self.app_id,
        )

        try:
            response = self.rate_limiter.call_with_retry(
                self.client.get_event_stream,
                ApplicationId=self.app_id,
            )
            stream = response.get("EventStream", {})
            result.resources = [stream]
            result.resource_count = 1
            result.metadata = {
                "destination_stream_arn": stream.get("DestinationStreamArn", ""),
                "role_arn": stream.get("RoleArn", ""),
                "has_event_stream": True,
            }
            self._increment_stat("Event Streams", 1)
        except Exception as e:
            error_code = ""
            if hasattr(e, "response"):
                error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NotFoundException":
                result.metadata = {"has_event_stream": False}
            else:
                result.errors.append(str(e))

        return result
