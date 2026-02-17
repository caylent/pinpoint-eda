"""Scanner for all Pinpoint channel types."""

from __future__ import annotations

from pinpoint_eda.scanners.base import BaseScanner, ScanResult

# All channel types and their get methods
CHANNEL_TYPES = {
    "Email": "get_email_channel",
    "SMS": "get_sms_channel",
    "Voice": "get_voice_channel",
    "APNS": "get_apns_channel",
    "APNSSandbox": "get_apns_sandbox_channel",
    "APNSVoip": "get_apns_voip_channel",
    "APNSVoipSandbox": "get_apns_voip_sandbox_channel",
    "GCM": "get_gcm_channel",
    "Baidu": "get_baidu_channel",
    "ADM": "get_adm_channel",
}

# Response keys for each channel type
CHANNEL_RESPONSE_KEYS = {
    "Email": "EmailChannelResponse",
    "SMS": "SMSChannelResponse",
    "Voice": "VoiceChannelResponse",
    "APNS": "APNSChannelResponse",
    "APNSSandbox": "APNSSandboxChannelResponse",
    "APNSVoip": "APNSVoipChannelResponse",
    "APNSVoipSandbox": "APNSVoipSandboxChannelResponse",
    "GCM": "GCMChannelResponse",
    "Baidu": "BaiduChannelResponse",
    "ADM": "ADMChannelResponse",
}


class ChannelsScanner(BaseScanner):
    name = "channels"
    description = "All channel types (Email, SMS, Voice, APNS, GCM, etc.)"
    per_app = True

    def scan(self) -> ScanResult:
        self._update_status(f"Scanning channels for {self.app_id}")

        result = ScanResult(
            scanner_name=self.name,
            region=self.region,
            app_id=self.app_id,
        )

        active_channels = []
        all_channels = []

        for channel_type, method_name in CHANNEL_TYPES.items():
            try:
                method = getattr(self.client, method_name)
                response = self.rate_limiter.call_with_retry(
                    method,
                    ApplicationId=self.app_id,
                )
                response_key = CHANNEL_RESPONSE_KEYS[channel_type]
                channel_data = response.get(response_key, {})
                channel_info = {
                    "type": channel_type,
                    "enabled": channel_data.get("Enabled", False),
                    "is_archived": channel_data.get("IsArchived", False),
                    "data": channel_data,
                }
                all_channels.append(channel_info)
                if channel_data.get("Enabled", False):
                    active_channels.append(channel_type)
            except Exception as e:
                error_code = ""
                if hasattr(e, "response"):
                    error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "NotFoundException":
                    # Channel not configured -- not an error
                    continue
                result.errors.append(f"{channel_type}: {e}")

        result.resources = all_channels
        result.resource_count = len(all_channels)
        result.metadata = {
            "active_channels": active_channels,
            "active_count": len(active_channels),
            "total_checked": len(CHANNEL_TYPES),
        }

        self._increment_stat("Channels", len(active_channels))
        return result
