"""Tests for region discovery."""

from unittest.mock import MagicMock

from pinpoint_eda.aws_session import AWSSessionManager
from pinpoint_eda.config import AccountConfig
from pinpoint_eda.region_discovery import discover_regions


class TestDiscoverRegions:
    def test_finds_apps_in_regions(self):
        account = AccountConfig(profile="test")
        session_manager = MagicMock(spec=AWSSessionManager)

        # Mock client that returns apps only for us-east-1
        def make_client(acct, region):
            client = MagicMock()
            if region == "us-east-1":
                client.get_apps.return_value = {
                    "ApplicationsResponse": {
                        "Item": [{"Id": "app-1"}, {"Id": "app-2"}]
                    }
                }
            else:
                client.get_apps.return_value = {
                    "ApplicationsResponse": {"Item": []}
                }
            return client

        session_manager.get_pinpoint_client.side_effect = make_client

        result = discover_regions(session_manager, account)

        assert "us-east-1" in result
        assert result["us-east-1"] == ["app-1", "app-2"]
        # Other regions should not appear (empty apps)
        for region in result:
            assert len(result[region]) > 0

    def test_handles_access_denied(self):
        from botocore.exceptions import ClientError

        account = AccountConfig()
        session_manager = MagicMock(spec=AWSSessionManager)

        def make_client(acct, region):
            client = MagicMock()
            client.get_apps.side_effect = ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "denied"},
                 "ResponseMetadata": {"HTTPStatusCode": 403}},
                "GetApps",
            )
            return client

        session_manager.get_pinpoint_client.side_effect = make_client

        result = discover_regions(session_manager, account)
        assert result == {}

    def test_empty_account(self):
        account = AccountConfig()
        session_manager = MagicMock(spec=AWSSessionManager)

        def make_client(acct, region):
            client = MagicMock()
            client.get_apps.return_value = {
                "ApplicationsResponse": {"Item": []}
            }
            return client

        session_manager.get_pinpoint_client.side_effect = make_client

        result = discover_regions(session_manager, account)
        assert result == {}
