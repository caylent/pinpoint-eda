"""Tests for channels scanner."""


from botocore.exceptions import ClientError

from pinpoint_eda.scanners.channels import ChannelsScanner


class TestChannelsScanner:
    def test_scan_with_active_channels(self, mock_pinpoint_client, rate_limiter):
        mock_pinpoint_client.get_email_channel.return_value = {
            "EmailChannelResponse": {"Enabled": True, "IsArchived": False}
        }
        mock_pinpoint_client.get_sms_channel.return_value = {
            "SMSChannelResponse": {"Enabled": True, "IsArchived": False}
        }
        # All other channels not found
        not_found = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "not found"},
             "ResponseMetadata": {"HTTPStatusCode": 404}},
            "GetChannel",
        )
        mock_pinpoint_client.get_voice_channel.side_effect = not_found
        mock_pinpoint_client.get_apns_channel.side_effect = not_found
        mock_pinpoint_client.get_apns_sandbox_channel.side_effect = not_found
        mock_pinpoint_client.get_apns_voip_channel.side_effect = not_found
        mock_pinpoint_client.get_apns_voip_sandbox_channel.side_effect = not_found
        mock_pinpoint_client.get_gcm_channel.side_effect = not_found
        mock_pinpoint_client.get_baidu_channel.side_effect = not_found
        mock_pinpoint_client.get_adm_channel.side_effect = not_found

        scanner = ChannelsScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
            app_id="app-1",
        )
        result = scanner.scan()

        assert result.resource_count == 2
        assert "Email" in result.metadata["active_channels"]
        assert "SMS" in result.metadata["active_channels"]
        assert result.metadata["active_count"] == 2
        assert not result.errors

    def test_scan_no_channels(self, mock_pinpoint_client, rate_limiter):
        not_found = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "not found"},
             "ResponseMetadata": {"HTTPStatusCode": 404}},
            "GetChannel",
        )
        for method_name in [
            "get_email_channel", "get_sms_channel", "get_voice_channel",
            "get_apns_channel", "get_apns_sandbox_channel", "get_apns_voip_channel",
            "get_apns_voip_sandbox_channel", "get_gcm_channel", "get_baidu_channel",
            "get_adm_channel",
        ]:
            getattr(mock_pinpoint_client, method_name).side_effect = not_found

        scanner = ChannelsScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
            app_id="app-1",
        )
        result = scanner.scan()

        assert result.resource_count == 0
        assert result.metadata["active_count"] == 0
