"""Parallel region probing to find Pinpoint applications."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from botocore.exceptions import ClientError, EndpointConnectionError

from pinpoint_eda.aws_session import AWSSessionManager
from pinpoint_eda.config import AccountConfig
from pinpoint_eda.progress import ProgressDisplay

logger = logging.getLogger(__name__)

# Regions where Pinpoint is available
PINPOINT_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-2",
    "ap-south-1",
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-southeast-1",
    "ap-southeast-2",
    "ca-central-1",
    "eu-central-1",
    "eu-west-1",
    "eu-west-2",
    "eu-north-1",
    "sa-east-1",
    "me-south-1",
    "af-south-1",
    "ap-east-1",
    "eu-south-1",
    "eu-west-3",
    "us-west-1",
]


def discover_regions(
    session_manager: AWSSessionManager,
    account: AccountConfig,
    progress: ProgressDisplay | None = None,
) -> dict[str, list[str]]:
    """Probe all Pinpoint regions in parallel to find apps.

    Returns:
        Dict mapping region -> list of application IDs found.
    """
    regions_with_apps: dict[str, list[str]] = {}

    if progress:
        progress.start_discovery(len(PINPOINT_REGIONS))

    def probe_region(region: str) -> tuple[str, list[str]]:
        try:
            client = session_manager.get_pinpoint_client(account, region)
            response = client.get_apps(PageSize="100")
            apps = response.get("ApplicationsResponse", {}).get("Item", [])
            app_ids = [app["Id"] for app in apps]
            return region, app_ids
        except (ClientError, EndpointConnectionError) as e:
            error_code = ""
            if isinstance(e, ClientError):
                error_code = e.response.get("Error", {}).get("Code", "")
            # Service not available in this region, or access denied
            if error_code in ("AccessDeniedException", "UnrecognizedClientException"):
                logger.debug("Pinpoint not accessible in %s: %s", region, error_code)
            else:
                logger.debug("Error probing %s: %s", region, e)
            return region, []
        finally:
            if progress:
                progress.advance_discovery()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(probe_region, region): region
            for region in PINPOINT_REGIONS
        }
        for future in as_completed(futures):
            region, app_ids = future.result()
            if app_ids:
                regions_with_apps[region] = app_ids
                logger.info("Found %d apps in %s", len(app_ids), region)

    total_apps = sum(len(apps) for apps in regions_with_apps.values())
    if progress:
        progress.finish_discovery(len(regions_with_apps), total_apps)

    return regions_with_apps
