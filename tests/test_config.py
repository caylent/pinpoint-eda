"""Tests for config models."""

from pathlib import Path

from pinpoint_eda.config import AccountConfig, ScanConfig


class TestAccountConfig:
    def test_label_with_alias(self):
        config = AccountConfig(alias="prod")
        assert config.label == "prod"

    def test_label_with_profile(self):
        config = AccountConfig(profile="my-profile")
        assert config.label == "my-profile"

    def test_label_with_role_arn(self):
        config = AccountConfig(role_arn="arn:aws:iam::123456789012:role/MyRole")
        assert config.label == "MyRole"

    def test_label_default(self):
        config = AccountConfig()
        assert config.label == "default"


class TestScanConfig:
    def test_defaults(self):
        config = ScanConfig()
        assert config.max_workers == 5
        assert config.kpi_days == 90
        assert config.output_dir == Path("./pinpoint-eda-output")
        assert config.resume is False
        assert config.json_only is False

    def test_config_hash_deterministic(self):
        config1 = ScanConfig(regions=["us-east-1", "eu-west-1"])
        config2 = ScanConfig(regions=["eu-west-1", "us-east-1"])
        assert config1.config_hash() == config2.config_hash()

    def test_config_hash_changes_with_scanners(self):
        config1 = ScanConfig(scanners=["segments"])
        config2 = ScanConfig(scanners=["campaigns"])
        assert config1.config_hash() != config2.config_hash()

    def test_config_hash_stable(self):
        config = ScanConfig()
        assert config.config_hash() == config.config_hash()
