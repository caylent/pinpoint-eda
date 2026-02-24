"""Scanner for Pinpoint KPIs (application, campaign, journey)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pinpoint_eda.scanners.base import BaseScanner, ScanResult

# Max date range the Pinpoint KPI API allows
MAX_KPI_WINDOW_DAYS = 31

# Valid application-level KPI names
APP_KPI_NAMES = [
    "unique-deliveries-grouped-by-date",
    "successful-delivery-rate-grouped-by-date",
    "txn-sms-delivered-grouped-by-date",
    "txn-sms-sent-grouped-by-date",
    "txn-emails-delivered-grouped-by-date",
    "txn-emails-sent-grouped-by-date",
]


def _extract_value(row: dict) -> float | None:
    """Extract numeric value from a KPI row."""
    # Pinpoint KPI rows have Values list with Type/Value pairs
    values = row.get("Values", [])
    for v in values:
        if v.get("Type") == "Double":
            return float(v.get("Value", 0))
        if v.get("Type") == "Long":
            return int(v.get("Value", 0))
    # Fallback: check for direct Value field
    if "Value" in row:
        try:
            return float(row["Value"])
        except (TypeError, ValueError):
            pass
    return None


def _sum_kpi_rows(kpi_data: dict) -> int:
    """Sum all values from KPI rows."""
    total = 0
    for row in kpi_data.get("rows", []):
        val = _extract_value(row)
        if val is not None:
            total += int(val)
    return total


def _avg_kpi_rows(kpi_data: dict) -> float | None:
    """Average all values from KPI rows (for rates)."""
    rows = kpi_data.get("rows", [])
    if not rows:
        return None
    values = []
    for row in rows:
        val = _extract_value(row)
        if val is not None:
            values.append(val)
    if not values:
        return None
    return round(sum(values) / len(values), 2)


class KPIsScanner(BaseScanner):
    name = "kpis"
    description = "Application, campaign, and journey KPIs"
    per_app = True

    def scan(self) -> ScanResult:
        self._update_status(f"Gathering KPIs for {self.app_id}")

        result = ScanResult(
            scanner_name=self.name,
            region=self.region,
            app_id=self.app_id,
        )

        kpi_data: dict = {"application": {}}

        # Query KPIs in 31-day windows to cover the full kpi_days range
        end_time = datetime.now(UTC)
        remaining_days = min(self.kpi_days, 90)  # Pinpoint keeps 90 days max

        while remaining_days > 0:
            window = min(remaining_days, MAX_KPI_WINDOW_DAYS)
            window_end = end_time
            window_start = window_end - timedelta(days=window)

            for kpi_name in APP_KPI_NAMES:
                try:
                    resp = self.rate_limiter.call_with_retry(
                        self.client.get_application_date_range_kpi,
                        ApplicationId=self.app_id,
                        KpiName=kpi_name,
                        StartTime=window_start,
                        EndTime=window_end,
                    )
                    kpi_result = resp.get(
                        "ApplicationDateRangeKpiResponse", {}
                    )
                    rows = kpi_result.get("KpiResult", {}).get("Rows", [])
                    existing = kpi_data["application"].get(kpi_name, {})
                    existing_rows = existing.get("rows", [])
                    kpi_data["application"][kpi_name] = {
                        "rows": existing_rows + rows,
                    }
                except Exception as e:
                    error_code = ""
                    if hasattr(e, "response"):
                        error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code != "NotFoundException":
                        result.errors.append(f"app_kpi_{kpi_name}: {e}")

            remaining_days -= window
            end_time = window_start

        result.resources = [kpi_data]
        result.resource_count = sum(
            len(v) for v in kpi_data.values() if isinstance(v, dict)
        )

        # Determine if app has recent activity and sum up metrics
        has_deliveries = False
        delivery_data = kpi_data["application"].get(
            "unique-deliveries-grouped-by-date", {}
        )
        if delivery_data.get("rows"):
            has_deliveries = True

        has_sms = bool(
            kpi_data["application"]
            .get("txn-sms-sent-grouped-by-date", {})
            .get("rows")
        )
        has_email = bool(
            kpi_data["application"]
            .get("txn-emails-sent-grouped-by-date", {})
            .get("rows")
        )

        # Aggregate KPI values
        metrics = {
            "unique_deliveries": _sum_kpi_rows(
                kpi_data["application"].get("unique-deliveries-grouped-by-date", {})
            ),
            "successful_delivery_rate": _avg_kpi_rows(
                kpi_data["application"].get("successful-delivery-rate-grouped-by-date", {})
            ),
            "sms_delivered": _sum_kpi_rows(
                kpi_data["application"].get("txn-sms-delivered-grouped-by-date", {})
            ),
            "sms_sent": _sum_kpi_rows(
                kpi_data["application"].get("txn-sms-sent-grouped-by-date", {})
            ),
            "emails_delivered": _sum_kpi_rows(
                kpi_data["application"].get("txn-emails-delivered-grouped-by-date", {})
            ),
            "emails_sent": _sum_kpi_rows(
                kpi_data["application"].get("txn-emails-sent-grouped-by-date", {})
            ),
        }

        result.metadata = {
            "kpi_days": self.kpi_days,
            "app_kpis_collected": len(kpi_data["application"]),
            "has_delivery_data": has_deliveries,
            "has_recent_sms": has_sms,
            "has_recent_email": has_email,
            "is_active": has_deliveries or has_sms or has_email,
            "metrics": metrics,
        }

        return result
