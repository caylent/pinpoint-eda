"""Tests for journeys scanner."""


from pinpoint_eda.scanners.journeys import JourneysScanner


class TestJourneysScanner:
    def test_scan_with_journeys(self, mock_pinpoint_client, rate_limiter):
        mock_pinpoint_client.list_journeys.return_value = {
            "JourneysResponse": {
                "Item": [
                    {"Id": "j-1", "Name": "Onboarding", "State": "ACTIVE"},
                    {"Id": "j-2", "Name": "Re-engagement", "State": "CLOSED"},
                ]
            }
        }
        mock_pinpoint_client.get_journey.return_value = {
            "JourneyResponse": {
                "Id": "j-1",
                "Activities": {
                    "a1": {"Email": {"MessageConfig": {}}},
                    "a2": {"Wait": {"WaitTime": {}}},
                },
            }
        }
        mock_pinpoint_client.get_journey_execution_metrics.return_value = {
            "JourneyExecutionMetricsResponse": {"Metrics": {"ENDPOINT_ENTERED": "100"}}
        }

        scanner = JourneysScanner(
            client=mock_pinpoint_client,
            rate_limiter=rate_limiter,
            region="us-east-1",
            app_id="app-1",
        )
        result = scanner.scan()

        assert result.resource_count == 2
        assert result.metadata["active"] == 1
        assert result.metadata["total_activities"] == 4  # 2 activities * 2 journeys (same mock)

    def test_classify_activity(self):
        assert JourneysScanner._classify_activity({"Email": {}}) == "Email"
        assert JourneysScanner._classify_activity({"Wait": {}}) == "Wait"
        assert JourneysScanner._classify_activity({"ConditionalSplit": {}}) == "ConditionalSplit"
        assert JourneysScanner._classify_activity({}) == "Unknown"
