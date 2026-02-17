"""Tests for pagination utilities."""

from unittest.mock import MagicMock

from pinpoint_eda.pagination import paginate_list, paginate_pinpoint
from pinpoint_eda.rate_limiter import RateLimiter


class TestPaginatePinpoint:
    def test_single_page(self):
        limiter = RateLimiter(requests_per_second=1000.0)
        mock_method = MagicMock(return_value={
            "SegmentsResponse": {
                "Item": [{"Id": "seg-1"}, {"Id": "seg-2"}],
            }
        })

        result = paginate_pinpoint(
            api_method=mock_method,
            rate_limiter=limiter,
            response_key="SegmentsResponse",
            ApplicationId="app-1",
        )

        assert len(result) == 2
        assert result[0]["Id"] == "seg-1"
        mock_method.assert_called_once()

    def test_multiple_pages(self):
        limiter = RateLimiter(requests_per_second=1000.0)
        call_count = 0

        def mock_api(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "SegmentsResponse": {
                        "Item": [{"Id": f"seg-{i}"} for i in range(100)],
                        "NextToken": "token-2",
                    }
                }
            return {
                "SegmentsResponse": {
                    "Item": [{"Id": f"seg-{i}"} for i in range(100, 150)],
                }
            }

        result = paginate_pinpoint(
            api_method=mock_api,
            rate_limiter=limiter,
            response_key="SegmentsResponse",
            ApplicationId="app-1",
        )

        assert len(result) == 150
        assert call_count == 2

    def test_empty_response(self):
        limiter = RateLimiter(requests_per_second=1000.0)
        mock_method = MagicMock(return_value={
            "SegmentsResponse": {"Item": []}
        })

        result = paginate_pinpoint(
            api_method=mock_method,
            rate_limiter=limiter,
            response_key="SegmentsResponse",
            ApplicationId="app-1",
        )

        assert result == []

    def test_progress_callback(self):
        limiter = RateLimiter(requests_per_second=1000.0)
        callbacks = []

        mock_method = MagicMock(return_value={
            "SegmentsResponse": {
                "Item": [{"Id": "seg-1"}],
            }
        })

        paginate_pinpoint(
            api_method=mock_method,
            rate_limiter=limiter,
            response_key="SegmentsResponse",
            progress_callback=lambda items, page: callbacks.append((items, page)),
            ApplicationId="app-1",
        )

        assert len(callbacks) == 1
        assert callbacks[0] == (1, 1)


class TestPaginateList:
    def test_single_page(self):
        limiter = RateLimiter(requests_per_second=1000.0)
        mock_method = MagicMock(return_value={
            "TemplatesResponse": {
                "Item": [{"TemplateName": "t1"}],
            }
        })

        result = paginate_list(
            api_method=mock_method,
            rate_limiter=limiter,
            response_key="TemplatesResponse",
        )

        assert len(result) == 1

    def test_multiple_pages_top_level_token(self):
        limiter = RateLimiter(requests_per_second=1000.0)
        call_count = 0

        def mock_api(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "TemplatesResponse": {
                        "Item": [{"TemplateName": f"t{i}"} for i in range(10)],
                    },
                    "NextToken": "page2",
                }
            return {
                "TemplatesResponse": {
                    "Item": [{"TemplateName": f"t{i}"} for i in range(10, 15)],
                },
            }

        result = paginate_list(
            api_method=mock_api,
            rate_limiter=limiter,
            response_key="TemplatesResponse",
        )

        assert len(result) == 15
        assert call_count == 2
