"""Scanner for Pinpoint message templates."""

from __future__ import annotations

from pinpoint_eda.pagination import paginate_list
from pinpoint_eda.scanners.base import BaseScanner, ScanResult

# Template types and their get methods + response keys
TEMPLATE_TYPES = {
    "EMAIL": ("get_email_template", "EmailTemplateResponse"),
    "SMS": ("get_sms_template", "SMSTemplateResponse"),
    "PUSH": ("get_push_template", "PushNotificationTemplateResponse"),
    "INAPP": ("get_in_app_template", "InAppTemplateResponse"),
    "VOICE": ("get_voice_template", "VoiceTemplateResponse"),
}


class TemplatesScanner(BaseScanner):
    name = "templates"
    description = "Email, SMS, Push, In-App, Voice templates"
    per_app = False

    def scan(self) -> ScanResult:
        self._update_status("Scanning message templates")

        result = ScanResult(
            scanner_name=self.name,
            region=self.region,
            app_id="account",
        )

        try:
            templates = paginate_list(
                api_method=self.client.list_templates,
                rate_limiter=self.rate_limiter,
                response_key="TemplatesResponse",
                items_key="Item",
            )

            type_counts: dict[str, int] = {}
            enriched_templates = []

            for tmpl in templates:
                tmpl_name = tmpl.get("TemplateName", "")
                tmpl_type = tmpl.get("TemplateType", "UNKNOWN")
                type_counts[tmpl_type] = type_counts.get(tmpl_type, 0) + 1

                # Get template detail
                if tmpl_type in TEMPLATE_TYPES:
                    method_name, response_key = TEMPLATE_TYPES[tmpl_type]
                    try:
                        method = getattr(self.client, method_name)
                        resp = self.rate_limiter.call_with_retry(
                            method,
                            TemplateName=tmpl_name,
                            Version="$LATEST",
                        )
                        detail = resp.get(response_key, {})
                        tmpl["_detail"] = {
                            "version": detail.get("Version", ""),
                            "last_modified": detail.get("LastModifiedDate", ""),
                            "default_substitutions": detail.get("DefaultSubstitutions"),
                        }
                    except Exception:
                        pass

                enriched_templates.append(tmpl)

            result.resources = enriched_templates
            result.resource_count = len(enriched_templates)
            result.metadata = {
                "total": len(enriched_templates),
                "type_breakdown": type_counts,
                "has_inapp": type_counts.get("INAPP", 0) > 0,
            }

            self._increment_stat("Templates", len(enriched_templates))
        except Exception as e:
            result.errors.append(str(e))

        return result
