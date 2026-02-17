"""Tests for segments scanner."""


from pinpoint_eda.scanners.segments import SegmentsScanner


class TestSegmentsScanner:
    def test_scan_with_segments(self, mock_pinpoint_client, rate_limiter):
        mock_pinpoint_client.get_segments.return_value = {
            "SegmentsResponse": {
                "Item": [
                    {"Id": "seg-1", "Name": "Active Users", "SegmentType": "DIMENSIONAL"},
                    {"Id": "seg-2", "Name": "Imported List", "SegmentType": "IMPORT"},
                    {"Id": "seg-3", "Name": "Another Segment", "SegmentType": "DIMENSIONAL"},
                ]
            }
        }
        mock_pinpoint_client.get_segment_versions.return_value = {
            "SegmentsResponse": {"Item": [{"Version": 1}]}
        }

        scanner = SegmentsScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
            app_id="app-1",
        )
        result = scanner.scan()

        assert result.resource_count == 3
        assert result.metadata["dynamic"] == 2
        assert result.metadata["imported"] == 1
        assert not result.errors

    def test_scan_empty(self, mock_pinpoint_client, rate_limiter):
        mock_pinpoint_client.get_segments.return_value = {
            "SegmentsResponse": {"Item": []}
        }

        scanner = SegmentsScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
            app_id="app-1",
        )
        result = scanner.scan()

        assert result.resource_count == 0
