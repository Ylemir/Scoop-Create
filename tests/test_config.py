"""Tests for config module: AppConfig, load_config, merge_config."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scoop_create.config import AppConfig, load_config, merge_config


class TestAppConfig:
    """Tests for AppConfig model."""

    def test_default_values(self) -> None:
        config = AppConfig()
        assert config.proxy == ""
        assert config.output_dir == ""
        assert config.include_pr is False
        assert config.interactive is False
        assert config.github_token == ""
        assert config.verify is True
        assert config.timeout == 20.0

    def test_timeout_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            AppConfig(timeout=-1)

    def test_custom_values(self) -> None:
        config = AppConfig(proxy="http://proxy:8080", output_dir="./out", timeout=30.0)
        assert config.proxy == "http://proxy:8080"
        assert config.output_dir == "./out"
        assert config.timeout == 30.0


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_defaults_when_no_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.proxy == ""
        assert config.output_dir == ""

    def test_load_from_explicit_path(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"proxy": "http://test:8080", "timeout": 15.0})
        )
        config = load_config(config_path=config_file)
        assert config.proxy == "http://test:8080"
        assert config.timeout == 15.0

    def test_load_from_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"output_dir": "./test-out"}))
        config = load_config()
        assert config.output_dir == "./test-out"

    def test_load_from_user_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user_config_dir = tmp_path / ".config" / "scoop-create"
        user_config_dir.mkdir(parents=True)
        config_file = user_config_dir / "config.json"
        config_file.write_text(json.dumps({"interactive": True}))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        monkeypatch.chdir(other_dir)
        config = load_config()
        assert config.interactive is True

    def test_load_nonexistent_explicit_path(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent.json"
        config = load_config(config_path=nonexistent)
        assert config.proxy == ""


class TestMergeConfig:
    """Tests for merge_config function."""

    def test_cli_overrides_file(self) -> None:
        config = AppConfig(proxy="http://file-proxy:8080")
        merged = merge_config(config, cli_proxy="http://cli-proxy:9090")
        assert merged.proxy == "http://cli-proxy:9090"

    def test_env_vars_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HTTP_PROXY", "http://env-proxy:8080")
        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        config = AppConfig()
        merged = merge_config(config)
        assert merged.proxy == "http://env-proxy:8080"
        assert merged.github_token == "env-token"

    def test_cli_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HTTP_PROXY", "http://env-proxy:8080")
        config = AppConfig()
        merged = merge_config(config, cli_proxy="http://cli-proxy:9090")
        assert merged.proxy == "http://cli-proxy:9090"

    def test_cli_output(self) -> None:
        config = AppConfig()
        merged = merge_config(config, cli_output="./custom-out")
        assert merged.output_dir == "./custom-out"

    def test_cli_interactive(self) -> None:
        config = AppConfig()
        merged = merge_config(config, cli_interactive=True)
        assert merged.interactive is True

    def test_cli_include_pr(self) -> None:
        config = AppConfig()
        merged = merge_config(config, cli_include_pr=True)
        assert merged.include_pr is True

    def test_cli_verify_false(self) -> None:
        config = AppConfig()
        merged = merge_config(config, cli_verify=False)
        assert merged.verify is False

    def test_cli_timeout(self) -> None:
        config = AppConfig()
        merged = merge_config(config, cli_timeout=45.0)
        assert merged.timeout == 45.0

    def test_file_config_preserved_when_no_cli_override(self) -> None:
        config = AppConfig(proxy="http://file-proxy:8080", output_dir="./file-out")
        merged = merge_config(config)
        assert merged.proxy == "http://file-proxy:8080"
        assert merged.output_dir == "./file-out"

    def test_ignore_manifest_fields_preserved(self) -> None:
        config = AppConfig(
            ignore_manifest_fields=["license", "architecture.64bit.hash"]
        )
        merged = merge_config(config)
        assert merged.ignore_manifest_fields == ["license", "architecture.64bit.hash"]
