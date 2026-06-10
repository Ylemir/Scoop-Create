"""Tests for service module: create_manifest, get_output_path (mocked)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scoop_create.config import AppConfig
from scoop_create.manifest import APP_TYPE_BOTH, APP_TYPE_CLI, APP_TYPE_GUI
from scoop_create.service import create_manifest, get_output_path, infer_app_type


class TestGetOutputPath:
    """Tests for get_output_path function."""

    def test_with_output_dir(self) -> None:
        config = AppConfig(output_dir="./output")
        path = get_output_path(config, "myrepo")
        assert path == Path("./output/myrepo.json")

    def test_without_output_dir(self) -> None:
        config = AppConfig()
        path = get_output_path(config, "myrepo")
        assert path == Path("myrepo.json")

    def test_lowercases_name(self) -> None:
        config = AppConfig()
        path = get_output_path(config, "MyRepo")
        assert path == Path("myrepo.json")

    def test_replaces_underscores_with_hyphens(self) -> None:
        config = AppConfig()
        path = get_output_path(config, "my_cool_repo")
        assert path == Path("my-cool-repo.json")

    def test_replaces_spaces_with_hyphens(self) -> None:
        config = AppConfig()
        path = get_output_path(config, "My Cool App")
        assert path == Path("my-cool-app.json")

    def test_collapses_multiple_hyphens(self) -> None:
        config = AppConfig()
        path = get_output_path(config, "my__repo--name")
        assert path == Path("my-repo-name.json")

    def test_strips_leading_trailing_hyphens(self) -> None:
        config = AppConfig()
        path = get_output_path(config, "--my-repo-")
        assert path == Path("my-repo.json")

    def test_normalized_with_output_dir(self) -> None:
        config = AppConfig(output_dir="./output")
        path = get_output_path(config, "My_Repo")
        assert path == Path("./output/my-repo.json")


class TestCreateManifest:
    """Tests for create_manifest function with mocked GitHub API."""

    @patch("scoop_create.service.fetch_repo_info")
    @patch("scoop_create.service.fetch_release")
    @patch("scoop_create.service.download_asset_for_hash")
    def test_basic_manifest_creation(
        self,
        mock_hash: MagicMock,
        mock_release: MagicMock,
        mock_repo: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_repo.return_value = {
            "name": "test-app",
            "description": "A test application",
            "license": {"spdx_id": "MIT", "name": "MIT License"},
            "homepage": "https://example.com",
        }
        mock_release.return_value = {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "test-app-1.0.0-x64.zip",
                    "browser_download_url": "https://example.com/test-app-1.0.0-x64.zip",
                }
            ],
        }
        mock_hash.return_value = "abc123def456"

        config = AppConfig(output_dir=str(tmp_path))
        result = create_manifest("owner/repo", config)

        assert result.owner == "owner"
        assert result.repo == "repo"
        assert result.app_name == "test-app"
        assert result.version == "1.0.0"
        assert result.description == "A test application"
        assert result.license_str == "MIT"
        assert result.asset_name == "test-app-1.0.0-x64.zip"
        assert result.asset_hash == "abc123def456"
        assert result.manifest.version == "1.0.0"

    @patch("scoop_create.service.fetch_repo_info")
    @patch("scoop_create.service.fetch_release")
    @patch("scoop_create.service.download_asset_for_hash")
    def test_strips_v_prefix_from_version(
        self,
        mock_hash: MagicMock,
        mock_release: MagicMock,
        mock_repo: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_repo.return_value = {
            "name": "app",
            "description": "Test",
            "license": {},
            "homepage": "",
        }
        mock_release.return_value = {
            "tag_name": "v2.0.0",
            "assets": [
                {
                    "name": "app.zip",
                    "browser_download_url": "https://example.com/app.zip",
                }
            ],
        }
        mock_hash.return_value = "hash123"

        config = AppConfig(output_dir=str(tmp_path))
        result = create_manifest("owner/repo", config)

        assert result.version == "2.0.0"

    @patch("scoop_create.service.fetch_repo_info")
    @patch("scoop_create.service.fetch_release")
    def test_no_assets_raises_error(
        self,
        mock_release: MagicMock,
        mock_repo: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_repo.return_value = {
            "name": "app",
            "description": "Test",
            "license": {},
            "homepage": "",
        }
        mock_release.return_value = {
            "tag_name": "v1.0.0",
            "assets": [],
        }

        config = AppConfig(output_dir=str(tmp_path))
        with pytest.raises(RuntimeError, match="No suitable release asset found"):
            create_manifest("owner/repo", config)

    @patch("scoop_create.service.fetch_repo_info")
    @patch("scoop_create.service.fetch_release")
    @patch("scoop_create.service.download_asset_for_hash")
    def test_uses_provided_version(
        self,
        mock_hash: MagicMock,
        mock_release: MagicMock,
        mock_repo: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_repo.return_value = {
            "name": "app",
            "description": "Test",
            "license": {},
            "homepage": "",
        }
        mock_release.return_value = {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "app.zip",
                    "browser_download_url": "https://example.com/app.zip",
                }
            ],
        }
        mock_hash.return_value = "hash123"

        config = AppConfig(output_dir=str(tmp_path))
        result = create_manifest("owner/repo", config, version="v2.0.0")

        assert result.version == "2.0.0"

    @patch("scoop_create.service.fetch_repo_info")
    @patch("scoop_create.service.fetch_release")
    @patch("scoop_create.service.download_asset_for_hash")
    def test_handles_empty_description(
        self,
        mock_hash: MagicMock,
        mock_release: MagicMock,
        mock_repo: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_repo.return_value = {
            "name": "app",
            "description": None,
            "license": {},
            "homepage": None,
        }
        mock_release.return_value = {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "app.zip",
                    "browser_download_url": "https://example.com/app.zip",
                }
            ],
        }
        mock_hash.return_value = "hash123"

        config = AppConfig(output_dir=str(tmp_path))
        result = create_manifest("owner/repo", config)

        assert result.description == ""
        assert result.homepage == "https://github.com/owner/repo"

    @patch("scoop_create.service.fetch_repo_info")
    @patch("scoop_create.service.fetch_release")
    @patch("scoop_create.service.download_asset_for_hash")
    def test_manifest_data_contains_architecture(
        self,
        mock_hash: MagicMock,
        mock_release: MagicMock,
        mock_repo: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_repo.return_value = {
            "name": "app",
            "description": "Test",
            "license": {"spdx_id": "MIT"},
            "homepage": "https://example.com",
        }
        mock_release.return_value = {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "app.zip",
                    "browser_download_url": "https://example.com/app.zip",
                }
            ],
        }
        mock_hash.return_value = "hash123"

        config = AppConfig(output_dir=str(tmp_path))
        result = create_manifest("owner/repo", config)

        assert "64bit" in result.manifest_data["architecture"]
        assert (
            result.manifest_data["architecture"]["64bit"]["url"]
            == "https://example.com/app.zip"
        )
        assert result.manifest_data["architecture"]["64bit"]["hash"] == "hash123"


class TestInferAppType:
    """Tests for infer_app_type function."""

    def test_infers_gui_from_topics(self) -> None:
        repo_info = {"topics": ["desktop-app", "gui"]}
        assets = [{"name": "app-1.0.0-x64.zip"}]
        assert infer_app_type(repo_info, assets) == APP_TYPE_GUI

    def test_infers_gui_from_asset_keywords(self) -> None:
        repo_info = {"topics": [], "description": "A tool"}
        assets = [{"name": "myapp-setup-1.0.0.exe"}]
        assert infer_app_type(repo_info, assets) == APP_TYPE_GUI

    def test_infers_cli_from_description(self) -> None:
        repo_info = {"description": "A blazing fast cli tool"}
        assets = [{"name": "tool-1.0.0-x64.zip"}]
        assert infer_app_type(repo_info, assets) == APP_TYPE_CLI

    def test_returns_both_when_mixed_signals(self) -> None:
        repo_info = {"description": "A cli desktop application"}
        assets = [{"name": "app.zip"}]
        assert infer_app_type(repo_info, assets) == APP_TYPE_BOTH

    def test_returns_both_by_default(self) -> None:
        repo_info = {"description": "A generic tool"}
        assets = [{"name": "app-1.0.0.zip"}]
        assert infer_app_type(repo_info, assets) == APP_TYPE_BOTH

    def test_handles_none_topics_and_description(self) -> None:
        repo_info = {"topics": None, "description": None}
        assets = [{"name": "app-setup.exe"}]
        assert infer_app_type(repo_info, assets) == APP_TYPE_GUI
