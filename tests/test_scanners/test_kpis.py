"""Tests for KPIs scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from pinpoint_eda.scanners.kpis import APP_KPI_NAMES, KPIsScanner


class TestKPIsScanner:
    def test_scan_aggregates_metrics_and_activity_flags(self, mock_pinpoint_client, rate_limiter):
        rows_by_kpi = {
            "unique-deliveries-grouped-by-date": [
                {"Values": [{"Type": "Long", "Value": "10"}]},
                {"Values": [{"Type": "Long", "Value": "5"}]},
            ],
            "successful-delivery-rate-grouped-by-date": [
                {"Values": [{"Type": "Double", "Value": "98.5"}]},
                {"Values": [{"Type": "Double", "Value": "97.5"}]},
            ],
            "txn-sms-delivered-grouped-by-date": [
                {"Values": [{"Type": "Long", "Value": "7"}]},
            ],
            "txn-sms-sent-grouped-by-date": [
                {"Values": [{"Type": "Long", "Value": "8"}]},
            ],
            "txn-emails-delivered-grouped-by-date": [
                {"Value": "3"},
            ],
            "txn-emails-sent-grouped-by-date": [
                {"Values": [{"Type": "Long", "Value": "4"}]},
                {"Value": "not-a-number"},
            ],
        }

        def _mock_get_kpi(**kwargs):
            kpi_name = kwargs["KpiName"]
            return {
                "ApplicationDateRangeKpiResponse": {
                    "KpiResult": {"Rows": rows_by_kpi[kpi_name]},
                }
            }

        mock_pinpoint_client.get_application_date_range_kpi.side_effect = _mock_get_kpi

        scanner = KPIsScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
            app_id="app-1",
            kpi_days=10,
        )
        result = scanner.scan()

        assert result.resource_count == len(APP_KPI_NAMES)
        assert result.metadata["app_kpis_collected"] == len(APP_KPI_NAMES)
        assert result.metadata["has_delivery_data"] is True
        assert result.metadata["has_recent_sms"] is True
        assert result.metadata["has_recent_email"] is True
        assert result.metadata["is_active"] is True
        assert result.metadata["metrics"] == {
            "unique_deliveries": 15,
            "successful_delivery_rate": 98.0,
            "sms_delivered": 7,
            "sms_sent": 8,
            "emails_delivered": 3,
            "emails_sent": 4,
        }
        assert not result.errors

    def test_scan_caps_to_ninety_days_in_thirty_one_day_windows(
        self, mock_pinpoint_client, rate_limiter
    ):
        mock_pinpoint_client.get_application_date_range_kpi.return_value = {
            "ApplicationDateRangeKpiResponse": {
                "KpiResult": {"Rows": [{"Values": [{"Type": "Long", "Value": "1"}]}]}
            }
        }

        scanner = KPIsScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
            app_id="app-1",
            kpi_days=120,
        )
        result = scanner.scan()

        call_count = mock_pinpoint_client.get_application_date_range_kpi.call_count
        assert call_count == len(APP_KPI_NAMES) * 3
        for call in mock_pinpoint_client.get_application_date_range_kpi.call_args_list:
            window = call.kwargs["EndTime"] - call.kwargs["StartTime"]
            assert window.days <= 31
            assert window.total_seconds() > 0
        assert result.metadata["metrics"]["unique_deliveries"] == 3
        assert result.metadata["metrics"]["sms_sent"] == 3
        assert result.metadata["metrics"]["emails_sent"] == 3
        assert result.metadata["metrics"]["successful_delivery_rate"] == 1.0

    def test_scan_ignores_not_found_errors(self, mock_pinpoint_client, rate_limiter):
        mock_pinpoint_client.get_application_date_range_kpi.side_effect = ClientError(
            {
                "Error": {"Code": "NotFoundException", "Message": "missing"},
                "ResponseMetadata": {"HTTPStatusCode": 404},
            },
            "GetApplicationDateRangeKpi",
        )

        scanner = KPIsScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
            app_id="app-1",
            kpi_days=5,
        )
        result = scanner.scan()

        assert result.resource_count == 0
        assert result.metadata["is_active"] is False
        assert result.metadata["metrics"]["successful_delivery_rate"] is None
        assert result.errors == []

    def test_scan_records_unexpected_kpi_errors(self, mock_pinpoint_client, rate_limiter):
        mock_pinpoint_client.get_application_date_range_kpi.side_effect = ClientError(
            {
                "Error": {"Code": "AccessDeniedException", "Message": "denied"},
                "ResponseMetadata": {"HTTPStatusCode": 403},
            },
            "GetApplicationDateRangeKpi",
        )

        scanner = KPIsScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
            app_id="app-1",
            kpi_days=1,
        )
        result = scanner.scan()

        assert len(result.errors) == len(APP_KPI_NAMES)
        assert all(err.startswith("app_kpi_") for err in result.errors)
