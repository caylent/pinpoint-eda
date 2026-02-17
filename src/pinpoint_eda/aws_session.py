"""AWS session management with multi-account and role assumption support."""

from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.config import Config

from pinpoint_eda.config import AccountConfig
from pinpoint_eda.exceptions import AWSSessionError, RoleAssumptionError

logger = logging.getLogger(__name__)

BOTO_CONFIG = Config(
    retries={"max_attempts": 3, "mode": "adaptive"},
    max_pool_connections=25,
)


class AWSSessionManager:
    """Manages AWS sessions for one or more accounts."""

    def __init__(self, accounts: list[AccountConfig]) -> None:
        self._accounts = accounts
        self._sessions: dict[str, boto3.Session] = {}

    def get_session(self, account: AccountConfig) -> boto3.Session:
        """Get or create a boto3 session for the given account config."""
        label = account.label
        if label in self._sessions:
            return self._sessions[label]

        try:
            if account.role_arn:
                session = self._assume_role(account)
            elif account.profile:
                session = boto3.Session(profile_name=account.profile)
            else:
                session = boto3.Session()
        except Exception as e:
            raise AWSSessionError(f"Failed to create session for {label}: {e}") from e

        self._sessions[label] = session
        return session

    def get_pinpoint_client(
        self, account: AccountConfig, region: str
    ) -> Any:
        """Create a Pinpoint client for a specific account and region."""
        session = self.get_session(account)
        return session.client("pinpoint", region_name=region, config=BOTO_CONFIG)

    def get_sms_voice_v2_client(
        self, account: AccountConfig, region: str
    ) -> Any:
        """Create a PinpointSMSVoiceV2 client for a specific account and region."""
        session = self.get_session(account)
        return session.client("pinpoint-sms-voice-v2", region_name=region, config=BOTO_CONFIG)

    def _assume_role(self, account: AccountConfig) -> boto3.Session:
        """Assume an IAM role and return a session with temporary credentials."""
        try:
            base_session = boto3.Session(
                profile_name=account.profile if account.profile else None
            )
            sts = base_session.client("sts")
            kwargs: dict = {
                "RoleArn": account.role_arn,
                "RoleSessionName": "pinpoint-eda",
                "DurationSeconds": 3600,
            }
            if account.external_id:
                kwargs["ExternalId"] = account.external_id

            resp = sts.assume_role(**kwargs)
            creds = resp["Credentials"]

            return boto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
            )
        except Exception as e:
            raise RoleAssumptionError(
                f"Failed to assume role {account.role_arn}: {e}"
            ) from e

    def resolve_account_id(self, account: AccountConfig) -> str:
        """Resolve the real AWS account ID via STS GetCallerIdentity."""
        session = self.get_session(account)
        try:
            sts = session.client("sts", config=BOTO_CONFIG)
            identity = sts.get_caller_identity()
            return identity["Account"]
        except Exception as e:
            logger.warning("Failed to resolve account ID for %s: %s", account.label, e)
            return "unknown"

    @property
    def accounts(self) -> list[AccountConfig]:
        return self._accounts
