"""Tests for complexity scoring engine."""

from pinpoint_eda.complexity import (
    ComplexityLevel,
    _score_journey,
    _score_to_level,
    assess_complexity,
)
from pinpoint_eda.scanners.base import ScanResult


class TestScoreToLevel:
    def test_low(self):
        assert _score_to_level(0) == ComplexityLevel.LOW
        assert _score_to_level(5) == ComplexityLevel.LOW
        assert _score_to_level(9) == ComplexityLevel.LOW

    def test_medium(self):
        assert _score_to_level(10) == ComplexityLevel.MEDIUM
        assert _score_to_level(20) == ComplexityLevel.MEDIUM
        assert _score_to_level(29) == ComplexityLevel.MEDIUM

    def test_high(self):
        assert _score_to_level(30) == ComplexityLevel.HIGH
        assert _score_to_level(50) == ComplexityLevel.HIGH
        assert _score_to_level(69) == ComplexityLevel.HIGH

    def test_very_high(self):
        assert _score_to_level(70) == ComplexityLevel.VERY_HIGH
        assert _score_to_level(100) == ComplexityLevel.VERY_HIGH
        assert _score_to_level(500) == ComplexityLevel.VERY_HIGH


class TestScoreJourney:
    def test_draft_simple(self):
        jc = {
            "id": "j-1", "name": "Test", "state": "DRAFT",
            "activity_count": 0, "branching_count": 0,
            "integration_count": 0,
        }
        score, explanation = _score_journey(jc)
        assert score == 2  # base 1 + activity 1

    def test_active_complex(self):
        jc = {
            "id": "j-2", "name": "Onboarding", "state": "ACTIVE",
            "activity_count": 12, "branching_count": 3,
            "integration_count": 1,
        }
        score, explanation = _score_journey(jc)
        # base 5 + activity 5 (>10) + branching 3*2 + integration 1*3 = 19
        assert score == 19
        assert "3 branches" in explanation
        assert "1 integrations" in explanation

    def test_completed_medium(self):
        jc = {
            "id": "j-3", "name": "Reengagement", "state": "COMPLETED",
            "activity_count": 5, "branching_count": 1,
            "integration_count": 0,
        }
        score, explanation = _score_journey(jc)
        # base 3 + activity 3 (3-10) + branching 1*2 = 8
        assert score == 8

    def test_paused(self):
        jc = {
            "id": "j-4", "name": "Paused", "state": "PAUSED",
            "activity_count": 2, "branching_count": 0,
            "integration_count": 0,
        }
        score, explanation = _score_journey(jc)
        # base 2 + activity 1 (<=3) = 3
        assert score == 3


class TestAssessComplexity:
    def test_empty_results(self):
        assessment = assess_complexity({})
        assert assessment.overall_score == 0
        assert assessment.overall_level == ComplexityLevel.LOW
        assert assessment.app_assessments == []

    def test_single_app_with_journeys(self):
        results = {
            "default:us-east-1": [
                ScanResult(
                    scanner_name="applications",
                    region="us-east-1",
                    app_id="app-1",
                    resource_count=1,
                    metadata={"name": "TestApp"},
                ),
                ScanResult(
                    scanner_name="journeys",
                    region="us-east-1",
                    app_id="app-1",
                    resource_count=2,
                    metadata={
                        "total": 2, "active": 1,
                        "state_breakdown": {"ACTIVE": 1, "DRAFT": 1},
                        "total_activities": 8,
                        "journey_complexities": [
                            {
                                "id": "j-1", "name": "Active Flow",
                                "state": "ACTIVE", "activity_count": 6,
                                "branching_count": 1,
                                "integration_count": 0,
                            },
                            {
                                "id": "j-2", "name": "Draft",
                                "state": "DRAFT", "activity_count": 2,
                                "branching_count": 0,
                                "integration_count": 0,
                            },
                        ],
                    },
                ),
            ]
        }

        assessment = assess_complexity(results)
        assert len(assessment.app_assessments) == 1
        app = assessment.app_assessments[0]
        assert app.app_name == "TestApp"
        # j-1: base 5 + activity 3 + branching 2 = 10
        # j-2: base 1 + activity 1 = 2
        assert app.total_score == 12

    def test_account_level_scored_separately(self):
        results = {
            "default:us-east-1": [
                ScanResult(
                    scanner_name="applications",
                    region="us-east-1",
                    app_id="app-1",
                    resource_count=1,
                    metadata={"name": "MyApp"},
                ),
                ScanResult(
                    scanner_name="sms_voice_v2",
                    region="us-east-1",
                    app_id="account",
                    resource_count=4,
                    metadata={
                        "phone_numbers": 4, "pools": 0,
                        "sender_ids": 0, "opt_out_lists": 1,
                        "registrations": 0, "configuration_sets": 0,
                    },
                ),
            ]
        }

        assessment = assess_complexity(results)
        # App should NOT include SMS/Voice V2 score
        app = assessment.app_assessments[0]
        assert app.total_score == 0

        # Account assessment should have the SMS/Voice V2 score
        assert len(assessment.account_assessments) == 1
        acct = assessment.account_assessments[0]
        assert acct.total_score == 8  # 4 phones * 2

        # Overall includes both
        assert assessment.overall_score == 8

    def test_multiple_apps_dont_duplicate_account(self):
        """Account resources should NOT inflate per-app scores."""
        results = {
            "default:us-east-1": [
                ScanResult(
                    scanner_name="applications",
                    region="us-east-1",
                    app_id="app-1",
                    resource_count=1,
                    metadata={"name": "App1"},
                ),
                ScanResult(
                    scanner_name="applications",
                    region="us-east-1",
                    app_id="app-2",
                    resource_count=1,
                    metadata={"name": "App2"},
                ),
                ScanResult(
                    scanner_name="sms_voice_v2",
                    region="us-east-1",
                    app_id="account",
                    resource_count=4,
                    metadata={
                        "phone_numbers": 4, "pools": 0,
                        "sender_ids": 0, "opt_out_lists": 1,
                        "registrations": 0, "configuration_sets": 0,
                    },
                ),
            ]
        }

        assessment = assess_complexity(results)
        # Both apps should have 0 score (no per-app resources)
        assert assessment.app_assessments[0].total_score == 0
        assert assessment.app_assessments[1].total_score == 0
        # Account scored once: 4 phones * 2 = 8
        assert assessment.overall_score == 8

    def test_channels_and_campaigns(self):
        results = {
            "default:us-east-1": [
                ScanResult(
                    scanner_name="applications",
                    region="us-east-1",
                    app_id="app-1",
                    resource_count=1,
                    metadata={"name": "BigApp"},
                ),
                ScanResult(
                    scanner_name="segments",
                    region="us-east-1",
                    app_id="app-1",
                    resource_count=10,
                    metadata={
                        "total": 10, "dynamic": 3, "imported": 2,
                    },
                ),
                ScanResult(
                    scanner_name="campaigns",
                    region="us-east-1",
                    app_id="app-1",
                    resource_count=5,
                    metadata={
                        "total": 5, "active": 2,
                        "state_breakdown": {"EXECUTING": 2, "COMPLETED": 3},
                    },
                ),
                ScanResult(
                    scanner_name="channels",
                    region="us-east-1",
                    app_id="app-1",
                    resource_count=3,
                    metadata={
                        "active_channels": ["Email", "SMS"],
                        "active_count": 2,
                    },
                ),
            ]
        }

        assessment = assess_complexity(results)
        app = assessment.app_assessments[0]

        # Segments: 10 + 3*3 + 2*2 = 23
        # Campaigns: 2*3 + 3*1 = 9
        # Channels: 2*2 = 4
        assert app.total_score == 23 + 9 + 4

    def test_serialization(self):
        results = {
            "default:us-east-1": [
                ScanResult(
                    scanner_name="applications",
                    region="us-east-1",
                    app_id="app-1",
                    resource_count=1,
                    metadata={"name": "App"},
                ),
            ]
        }
        assessment = assess_complexity(results)
        data = assessment.to_dict()
        assert "overall_score" in data
        assert "app_assessments" in data
        assert "account_assessments" in data
        assert "migration_targets" in data
