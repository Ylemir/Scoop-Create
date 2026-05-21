"""Tests for CLI module using Typer's test client."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from scoop_create.cli import app

runner = CliRunner()


class TestCliVersion:
    """Tests for --version flag."""

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "scoop-create" in result.stdout


class TestCliHelp:
    """Tests for --help flag."""

    def test_help_flag(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Generate a Scoop app manifest" in result.stdout

    def test_no_args_shows_help(self) -> None:
        result = runner.invoke(app, [])
        assert result.exit_code == 2
        assert "Usage" in result.output


class TestCliInvalidUrl:
    """Tests for invalid GitHub URL handling."""

    def test_invalid_url(self) -> None:
        result = runner.invoke(app, ["not-a-github-url"])
        assert result.exit_code == 1
        assert "Error" in result.stdout


class TestCliDryRun:
    """Tests for --dry-run flag with mocked GitHub API."""

    @patch("scoop_create.service.fetch_repo_info")
    @patch("scoop_create.service.fetch_release")
    @patch("scoop_create.service.download_asset_for_hash")
    def test_dry_run(
        self,
        mock_hash: MagicMock,
        mock_release: MagicMock,
        mock_repo: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_repo.return_value = {
            "name": "test-app",
            "description": "A test app",
            "license": {"spdx_id": "MIT"},
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
        mock_hash.return_value = "abc123"

        result = runner.invoke(
            app,
            ["owner/repo", "--dry-run", "-o", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert "Dry-run mode" in result.stdout
        assert "test-app" in result.stdout

    @patch("scoop_create.service.fetch_repo_info")
    @patch("scoop_create.service.fetch_release")
    @patch("scoop_create.service.download_asset_for_hash")
    def test_dry_run_does_not_write_file(
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

        manifest_path = tmp_path / "repo.json"
        result = runner.invoke(
            app,
            ["owner/repo", "--dry-run", "-o", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert not manifest_path.exists()


class TestCliNormalRun:
    """Tests for normal manifest writing with mocked GitHub API."""

    @patch("scoop_create.service.fetch_repo_info")
    @patch("scoop_create.service.fetch_release")
    @patch("scoop_create.service.download_asset_for_hash")
    def test_writes_manifest(
        self,
        mock_hash: MagicMock,
        mock_release: MagicMock,
        mock_repo: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_repo.return_value = {
            "name": "app",
            "description": "Test app",
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

        result = runner.invoke(
            app,
            ["owner/repo", "-o", str(tmp_path)],
        )

        assert result.exit_code == 0
        manifest_path = tmp_path / "repo.json"
        assert manifest_path.exists()
        assert "Manifest written to" in result.stdout

    @patch("scoop_create.service.fetch_repo_info")
    @patch("scoop_create.service.fetch_release")
    @patch("scoop_create.service.download_asset_for_hash")
    def test_output_option(
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

        output_dir = tmp_path / "out"
        result = runner.invoke(
            app,
            ["owner/repo", "-o", str(output_dir)],
        )

        assert result.exit_code == 0
        assert (output_dir / "repo.json").exists()


class TestCliTlsVerification:
    """Tests for --verify/--no-verify flags."""

    @patch("scoop_create.service.fetch_repo_info")
    @patch("scoop_create.service.fetch_release")
    @patch("scoop_create.service.download_asset_for_hash")
    def test_no_verify_tls(
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

        result = runner.invoke(
            app,
            ["owner/repo", "--dry-run", "--no-verify"],
        )

        assert result.exit_code == 0
