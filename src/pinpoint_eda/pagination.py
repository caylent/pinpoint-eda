"""Generic Pinpoint paginator with page counting and progress callbacks."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from pinpoint_eda.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# API methods that use top-level NextToken instead of nested Token
TOP_LEVEL_TOKEN_METHODS = {
    "list_templates",
    "list_journeys",
}

# API methods that use nested response key with Token
NESTED_TOKEN_METHODS = {
    "get_segments": ("SegmentsResponse", "Item"),
    "get_campaigns": ("CampaignsResponse", "Item"),
    "get_import_jobs": ("ImportJobsResponse", "Item"),
    "get_export_jobs": ("ExportJobsResponse", "Item"),
    "get_apps": ("ApplicationsResponse", "Item"),
    "get_segment_versions": ("SegmentsResponse", "Item"),
    "get_campaign_versions": ("CampaignsResponse", "Item"),
    "get_recommender_configurations": ("ListRecommenderConfigurationsResponse", "Item"),
}


def paginate_pinpoint(
    api_method: Callable,
    rate_limiter: RateLimiter,
    response_key: str,
    items_key: str = "Item",
    page_size: int = 100,
    progress_callback: Callable[[int, int], None] | None = None,
    **api_kwargs: Any,
) -> list[dict]:
    """Generic Pinpoint paginator with progress callbacks.

    Args:
        api_method: The boto3 API method to call.
        rate_limiter: Rate limiter instance.
        response_key: Top-level key in the response (e.g., "SegmentsResponse").
        items_key: Key within the response for the list of items (e.g., "Item").
        page_size: Number of items per page.
        progress_callback: Called with (items_so_far, page_num) after each page.
        **api_kwargs: Additional arguments passed to the API method.

    Returns:
        List of all items across all pages.
    """
    all_items: list[dict] = []
    token: str | None = None
    page_num = 0
    method_name = getattr(api_method, "__name__", "")

    while True:
        kwargs = {**api_kwargs, "PageSize": str(page_size)}
        if token:
            kwargs["Token"] = token

        response = rate_limiter.call_with_retry(api_method, **kwargs)
        page_num += 1

        # Extract items from response
        nested = response.get(response_key, {})
        items = nested.get(items_key, [])
        all_items.extend(items)

        if progress_callback:
            progress_callback(len(all_items), page_num)

        # Check for next page
        next_token = nested.get("NextToken")
        if not next_token or not items:
            break
        token = next_token

    logger.debug(
        "%s: fetched %d items across %d pages",
        method_name,
        len(all_items),
        page_num,
    )
    return all_items


def paginate_list(
    api_method: Callable,
    rate_limiter: RateLimiter,
    response_key: str,
    items_key: str = "Item",
    page_size: int = 100,
    progress_callback: Callable[[int, int], None] | None = None,
    **api_kwargs: Any,
) -> list[dict]:
    """Paginator for list_* operations that use top-level NextToken.

    Used for list_templates, list_journeys, etc.
    """
    all_items: list[dict] = []
    token: str | None = None
    page_num = 0

    while True:
        kwargs = {**api_kwargs, "PageSize": str(page_size)}
        if token:
            kwargs["NextToken"] = token

        response = rate_limiter.call_with_retry(api_method, **kwargs)
        page_num += 1

        nested = response.get(response_key, {})
        items = nested.get(items_key, [])
        all_items.extend(items)

        if progress_callback:
            progress_callback(len(all_items), page_num)

        next_token = nested.get("NextToken") or response.get("NextToken")
        if not next_token or not items:
            break
        token = next_token

    return all_items


def paginate_v2(
    client: Any,
    method_name: str,
    rate_limiter: RateLimiter,
    result_key: str,
    max_results: int = 100,
    progress_callback: Callable[[int, int], None] | None = None,
    **api_kwargs: Any,
) -> list[dict]:
    """Paginator for PinpointSMSVoiceV2 describe_* operations using boto3 paginators."""
    all_items: list[dict] = []
    page_num = 0

    try:
        paginator = client.get_paginator(method_name)
        for page in paginator.paginate(
            **api_kwargs,
            PaginationConfig={"MaxItems": 1000, "PageSize": max_results},
        ):
            page_num += 1
            items = page.get(result_key, [])
            all_items.extend(items)
            if progress_callback:
                progress_callback(len(all_items), page_num)
    except client.exceptions.ClientError:
        raise
    except Exception:
        # Fallback: manual pagination if paginator not available
        token = None
        while True:
            kwargs = {**api_kwargs, "MaxResults": max_results}
            if token:
                kwargs["NextToken"] = token
            response = rate_limiter.call_with_retry(getattr(client, method_name), **kwargs)
            page_num += 1
            items = response.get(result_key, [])
            all_items.extend(items)
            if progress_callback:
                progress_callback(len(all_items), page_num)
            token = response.get("NextToken")
            if not token or not items:
                break

    return all_items
