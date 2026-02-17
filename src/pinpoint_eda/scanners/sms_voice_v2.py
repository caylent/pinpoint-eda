"""Scanner for PinpointSMSVoiceV2 resources."""

from __future__ import annotations

import logging

from pinpoint_eda.scanners.base import BaseScanner, ScanResult

logger = logging.getLogger(__name__)


class SMSVoiceV2Scanner(BaseScanner):
    name = "sms_voice_v2"
    description = "Phone numbers, pools, sender IDs, opt-out lists, registrations"
    per_app = False

    def scan(self) -> ScanResult:
        self._update_status("Scanning SMS/Voice V2 resources")

        result = ScanResult(
            scanner_name=self.name,
            region=self.region,
            app_id="account",
        )

        resources: dict = {}

        # Phone numbers
        resources["phone_numbers"] = self._safe_describe("describe_phone_numbers", "PhoneNumbers")
        # Pools
        resources["pools"] = self._safe_describe("describe_pools", "Pools")
        # Sender IDs
        resources["sender_ids"] = self._safe_describe("describe_sender_ids", "SenderIds")
        # Opt-out lists
        resources["opt_out_lists"] = self._safe_describe("describe_opt_out_lists", "OptOutLists")
        # Registrations
        resources["registrations"] = self._safe_describe("describe_registrations", "Registrations")
        # Configuration sets
        resources["configuration_sets"] = self._safe_describe(
            "describe_configuration_sets", "ConfigurationSets"
        )
        # Keywords (per phone number)
        resources["keywords"] = []
        for phone in resources.get("phone_numbers", []):
            phone_id = phone.get("PhoneNumberId", "")
            if phone_id:
                kw = self._safe_describe(
                    "describe_keywords",
                    "Keywords",
                    OriginationIdentity=phone_id,
                )
                for k in kw:
                    k["_phone_number_id"] = phone_id
                resources["keywords"].extend(kw)

        total = sum(len(v) for v in resources.values() if isinstance(v, list))
        result.resources = [resources]
        result.resource_count = total
        result.metadata = {
            "phone_numbers": len(resources.get("phone_numbers", [])),
            "pools": len(resources.get("pools", [])),
            "sender_ids": len(resources.get("sender_ids", [])),
            "opt_out_lists": len(resources.get("opt_out_lists", [])),
            "registrations": len(resources.get("registrations", [])),
            "configuration_sets": len(resources.get("configuration_sets", [])),
        }

        self._increment_stat("SMS/Voice V2", total)
        return result

    def _safe_describe(self, method_name: str, result_key: str, **kwargs) -> list:
        """Call a describe method, returning empty list on error."""
        try:
            method = getattr(self.client, method_name)
            all_items = []
            token = None
            while True:
                call_kwargs = {**kwargs, "MaxResults": 100}
                if token:
                    call_kwargs["NextToken"] = token
                resp = self.rate_limiter.call_with_retry(method, **call_kwargs)
                items = resp.get(result_key, [])
                all_items.extend(items)
                token = resp.get("NextToken")
                if not token or not items:
                    break
            return all_items
        except Exception as e:
            error_code = ""
            if hasattr(e, "response"):
                error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("AccessDeniedException", "ValidationException"):
                logger.debug("SMS Voice V2 %s not available: %s", method_name, error_code)
            else:
                logger.warning("SMS Voice V2 %s failed: %s", method_name, e)
            return []
