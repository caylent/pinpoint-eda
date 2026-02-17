"""Tests for applications scanner."""


from pinpoint_eda.scanners.applications import ApplicationsScanner


class TestApplicationsScanner:
    def test_scan_basic(self, mock_pinpoint_client, rate_limiter):
        mock_pinpoint_client.get_app.return_value = {
            "ApplicationResponse": {
                "Id": "app-1",
                "Name": "TestApp",
                "Arn": "arn:aws:mobiletargeting:us-east-1:123456789012:apps/app-1",
                "CreationDate": "2024-01-01T00:00:00Z",
            }
        }
        mock_pinpoint_client.list_tags_for_resource.return_value = {
            "TagsModel": {"tags": {"env": "prod"}}
        }

        scanner = ApplicationsScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
            app_id="app-1",
        )
        result = scanner.scan()

        assert result.resource_count == 1
        assert result.metadata["name"] == "TestApp"
        assert result.metadata["tags"] == {"env": "prod"}
        assert not result.errors

    def test_scan_handles_error(self, mock_pinpoint_client, rate_limiter):
        mock_pinpoint_client.get_app.side_effect = Exception("connection error")

        scanner = ApplicationsScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
            app_id="app-1",
        )
        result = scanner.scan()

        assert result.resource_count == 0
        assert len(result.errors) == 1
