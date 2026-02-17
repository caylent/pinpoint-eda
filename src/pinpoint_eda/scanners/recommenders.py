"""Scanner for Pinpoint recommender configurations."""

from __future__ import annotations

from pinpoint_eda.pagination import paginate_pinpoint
from pinpoint_eda.scanners.base import BaseScanner, ScanResult


class RecommendersScanner(BaseScanner):
    name = "recommenders"
    description = "ML recommender configurations"
    per_app = False

    def scan(self) -> ScanResult:
        self._update_status("Scanning recommender configurations")

        result = ScanResult(
            scanner_name=self.name,
            region=self.region,
            app_id="account",
        )

        try:
            recommenders = paginate_pinpoint(
                api_method=self.client.get_recommender_configurations,
                rate_limiter=self.rate_limiter,
                response_key="ListRecommenderConfigurationsResponse",
                items_key="Item",
            )

            result.resources = recommenders
            result.resource_count = len(recommenders)
            result.metadata = {
                "total": len(recommenders),
                "recommendation_providers": [
                    r.get("RecommendationProviderUri", "") for r in recommenders
                ],
            }

            self._increment_stat("Recommenders", len(recommenders))
        except Exception as e:
            result.errors.append(str(e))

        return result
