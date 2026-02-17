"""Pydantic models for scan configuration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field


class AccountConfig(BaseModel):
    """Configuration for a single AWS account."""

    profile: str | None = None
    role_arn: str | None = None
    external_id: str | None = None
    alias: str | None = None

    @property
    def label(self) -> str:
        if self.alias:
            return self.alias
        if self.profile:
            return self.profile
        if self.role_arn:
            return self.role_arn.split("/")[-1]
        return "default"


class ScanConfig(BaseModel):
    """Full scan configuration."""

    accounts: list[AccountConfig] = Field(default_factory=lambda: [AccountConfig()])
    regions: list[str] = Field(default_factory=list)
    app_ids: list[str] = Field(default_factory=list)
    scanners: list[str] = Field(default_factory=list)
    max_workers: int = Field(default=5, ge=1, le=50)
    kpi_days: int = Field(default=90, ge=1, le=365)
    output_dir: Path = Field(default=Path("./pinpoint-eda-output"))
    resume: bool = False
    fresh: bool = False
    json_only: bool = False
    verbose: bool = False
    no_sms_voice_v2: bool = False
    dry_run: bool = False

    def config_hash(self) -> str:
        """Deterministic hash of config for checkpoint matching."""
        key_fields = {
            "accounts": [a.model_dump() for a in self.accounts],
            "regions": sorted(self.regions),
            "app_ids": sorted(self.app_ids),
            "scanners": sorted(self.scanners),
            "no_sms_voice_v2": self.no_sms_voice_v2,
        }
        blob = json.dumps(key_fields, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]
