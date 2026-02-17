"""Tests for the interactive configurator."""

from pinpoint_eda.configurator import _discover_aws_profiles


class TestDiscoverAwsProfiles:
    def test_discovers_from_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / ".aws" / "config"
        config_file.parent.mkdir(parents=True)
        config_file.write_text(
            "[default]\nregion = us-east-1\n\n"
            "[profile prod]\nregion = us-west-2\n\n"
            "[profile staging]\nregion = eu-west-1\n"
        )
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        profiles = _discover_aws_profiles()
        assert profiles == ["default", "prod", "staging"]

    def test_discovers_from_credentials(self, tmp_path, monkeypatch):
        creds_file = tmp_path / ".aws" / "credentials"
        creds_file.parent.mkdir(parents=True)
        creds_file.write_text(
            "[default]\naws_access_key_id = AKIA...\n\n"
            "[dev]\naws_access_key_id = AKIA...\n"
        )
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        profiles = _discover_aws_profiles()
        assert profiles == ["default", "dev"]

    def test_merges_config_and_credentials(self, tmp_path, monkeypatch):
        aws_dir = tmp_path / ".aws"
        aws_dir.mkdir(parents=True)
        (aws_dir / "config").write_text(
            "[default]\nregion = us-east-1\n\n"
            "[profile alpha]\nregion = us-east-1\n"
        )
        (aws_dir / "credentials").write_text(
            "[default]\naws_access_key_id = AKIA...\n\n"
            "[beta]\naws_access_key_id = AKIA...\n"
        )
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        profiles = _discover_aws_profiles()
        # Merged and sorted, no duplicates
        assert profiles == ["alpha", "beta", "default"]

    def test_no_aws_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        profiles = _discover_aws_profiles()
        assert profiles == []

    def test_empty_config_files(self, tmp_path, monkeypatch):
        aws_dir = tmp_path / ".aws"
        aws_dir.mkdir(parents=True)
        (aws_dir / "config").write_text("")
        (aws_dir / "credentials").write_text("")
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        profiles = _discover_aws_profiles()
        assert profiles == []
