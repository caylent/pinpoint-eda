"""Custom exceptions for Pinpoint EDA."""


class PinpointEDAError(Exception):
    """Base exception for all Pinpoint EDA errors."""


class AWSSessionError(PinpointEDAError):
    """Failed to create or configure an AWS session."""


class RoleAssumptionError(AWSSessionError):
    """Failed to assume an IAM role."""


class RegionDiscoveryError(PinpointEDAError):
    """Failed during region discovery."""


class ScanError(PinpointEDAError):
    """Error during scanning."""


class ScannerError(ScanError):
    """Error within an individual scanner."""


class RateLimitExceededError(ScanError):
    """Rate limit exceeded after all retries."""


class CheckpointError(PinpointEDAError):
    """Error reading or writing checkpoint."""


class ConfigMismatchError(CheckpointError):
    """Checkpoint config doesn't match current scan config."""


class ReportError(PinpointEDAError):
    """Error generating report."""
