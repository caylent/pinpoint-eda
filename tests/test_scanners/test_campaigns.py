"""Tests for campaigns scanner."""


from pinpoint_eda.scanners.campaigns import CampaignsScanner


class TestCampaignsScanner:
    def test_scan_with_campaigns(self, mock_pinpoint_client, rate_limiter):
        mock_pinpoint_client.get_campaigns.return_value = {
            "CampaignsResponse": {
                "Item": [
                    {
                        "Id": "camp-1",
                        "Name": "Welcome Campaign",
                        "State": {"CampaignStatus": "EXECUTING"},
                    },
                    {
                        "Id": "camp-2",
                        "Name": "Old Campaign",
                        "State": {"CampaignStatus": "COMPLETED"},
                    },
                ]
            }
        }
        mock_pinpoint_client.get_campaign_versions.return_value = {
            "CampaignsResponse": {"Item": [{"Version": 1}]}
        }

        scanner = CampaignsScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
            app_id="app-1",
        )
        result = scanner.scan()

        assert result.resource_count == 2
        assert result.metadata["active"] == 1
        assert result.metadata["state_breakdown"]["EXECUTING"] == 1
        assert result.metadata["state_breakdown"]["COMPLETED"] == 1
