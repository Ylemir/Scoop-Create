"""Tests for utils module: HTTP client, URL parsing, and asset ranking."""

import pytest

from scoop_create.utils import get_http_client, guess_best_asset, parse_github_url


class TestParseGithubUrl:
    """Tests for parse_github_url function."""

    def test_full_https_url(self) -> None:
        owner, repo = parse_github_url("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_full_url_with_trailing_slash(self) -> None:
        owner, repo = parse_github_url("https://github.com/owner/repo/")
        assert owner == "owner"
        assert repo == "repo"

    def test_short_format(self) -> None:
        owner, repo = parse_github_url("owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_short_format_with_trailing_slash(self) -> None:
        owner, repo = parse_github_url("owner/repo/")
        assert owner == "owner"
        assert repo == "repo"

    def test_url_without_slash_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            parse_github_url("just-a-repo-name")

    def test_invalid_url_single_word(self) -> None:
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            parse_github_url("repo")

    def test_url_with_subpaths(self) -> None:
        owner, repo = parse_github_url("https://github.com/owner/repo/issues")
        assert owner == "owner"
        assert repo == "repo"


class TestGuessBestAsset:
    """Tests for guess_best_asset function."""

    def test_empty_assets(self) -> None:
        assert guess_best_asset([]) is None

    def test_single_windows_zip(self) -> None:
        assets = [
            {
                "name": "app-1.0-x64.zip",
                "browser_download_url": "https://example.com/app.zip",
            }
        ]
        result = guess_best_asset(assets)
        assert result is not None
        assert result["name"] == "app-1.0-x64.zip"

    def test_prefers_windows(self) -> None:
        assets = [
            {"name": "app-1.0-linux.tar.gz"},
            {"name": "app-1.0-win-x64.zip"},
        ]
        result = guess_best_asset(assets)
        assert result is not None
        assert "win" in result["name"].lower()

    def test_prefers_x64_over_x86(self) -> None:
        assets = [
            {"name": "app-1.0-win-x86.zip"},
            {"name": "app-1.0-win-x64.zip"},
        ]
        result = guess_best_asset(assets)
        assert result is not None
        assert "x64" in result["name"]

    def test_prefers_zip_over_exe(self) -> None:
        assets = [
            {"name": "app-1.0-win-x64.exe"},
            {"name": "app-1.0-win-x64.zip"},
        ]
        result = guess_best_asset(assets)
        assert result is not None
        assert result["name"].endswith(".zip")

    def test_excludes_source_code(self) -> None:
        assets = [
            {"name": "source-code.zip"},
            {"name": "app-1.0-win-x64.zip"},
        ]
        result = guess_best_asset(assets)
        assert result is not None
        assert result["name"] == "app-1.0-win-x64.zip"

    def test_excludes_macos(self) -> None:
        assets = [
            {"name": "app-1.0-macos.dmg"},
            {"name": "app-1.0-win-x64.zip"},
        ]
        result = guess_best_asset(assets)
        assert result is not None
        assert "win" in result["name"].lower()

    def test_excludes_linux(self) -> None:
        assets = [
            {"name": "app-1.0-linux.tar.gz"},
            {"name": "app-1.0-win-x64.zip"},
        ]
        result = guess_best_asset(assets)
        assert result is not None
        assert "win" in result["name"].lower()

    def test_complex_ranking(self) -> None:
        assets = [
            {"name": "app-1.0-arm64.zip"},
            {"name": "source.tar.gz"},
            {"name": "app-1.0-win-x86.exe"},
            {"name": "app-1.0-win-x64.zip"},
            {"name": "app-1.0-linux.tar.gz"},
        ]
        result = guess_best_asset(assets)
        assert result is not None
        assert result["name"] == "app-1.0-win-x64.zip"

    def test_prefers_portable(self) -> None:
        assets = [
            {"name": "app-1.0-win-x64-portable.zip"},
            {"name": "app-1.0-win-x64.zip"},
        ]
        result = guess_best_asset(assets)
        assert result is not None
        assert "portable" in result["name"].lower()


class TestGetHttpClient:
    """Tests for get_http_client function."""

    def test_default_client(self) -> None:
        client = get_http_client()
        assert client is not None
        client.close()

    def test_client_with_token(self) -> None:
        client = get_http_client(token="test-token")
        assert client.headers["Authorization"] == "token test-token"
        client.close()

    def test_client_with_proxy(self) -> None:
        client = get_http_client(proxy="http://localhost:8080")
        assert client is not None
        client.close()

    def test_client_without_verify(self) -> None:
        client = get_http_client(verify=False)
        assert client is not None
        client.close()
