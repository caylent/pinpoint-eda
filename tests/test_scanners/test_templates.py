"""Tests for templates scanner."""


from pinpoint_eda.scanners.templates import TemplatesScanner


class TestTemplatesScanner:
    def test_scan_with_templates(self, mock_pinpoint_client, rate_limiter):
        mock_pinpoint_client.list_templates.return_value = {
            "TemplatesResponse": {
                "Item": [
                    {"TemplateName": "welcome-email", "TemplateType": "EMAIL"},
                    {"TemplateName": "alert-sms", "TemplateType": "SMS"},
                    {"TemplateName": "promo-push", "TemplateType": "PUSH"},
                ]
            }
        }
        mock_pinpoint_client.get_email_template.return_value = {
            "EmailTemplateResponse": {"Version": "1", "LastModifiedDate": "2024-01-01"}
        }
        mock_pinpoint_client.get_sms_template.return_value = {
            "SMSTemplateResponse": {"Version": "1", "LastModifiedDate": "2024-01-01"}
        }
        mock_pinpoint_client.get_push_template.return_value = {
            "PushNotificationTemplateResponse": {"Version": "1", "LastModifiedDate": "2024-01-01"}
        }

        scanner = TemplatesScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
        )
        result = scanner.scan()

        assert result.resource_count == 3
        assert result.metadata["type_breakdown"]["EMAIL"] == 1
        assert result.metadata["type_breakdown"]["SMS"] == 1
        assert result.metadata["type_breakdown"]["PUSH"] == 1
        assert result.metadata["has_inapp"] is False

    def test_scan_empty(self, mock_pinpoint_client, rate_limiter):
        mock_pinpoint_client.list_templates.return_value = {
            "TemplatesResponse": {"Item": []}
        }

        scanner = TemplatesScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
        )
        result = scanner.scan()

        assert result.resource_count == 0
