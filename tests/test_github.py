"""Tests for github module: API client functions (mocked)."""

from unittest.mock import MagicMock

import httpx
import pytest

from scoop_create.github import (
    _check_response,
    download_asset_for_hash,
    fetch_release,
    fetch_repo_info,
)


class TestCheckResponse:
    """Tests for _check_response helper."""

    def test_ok_response(self) -> None:
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        _check_response(response, "test")

    def test_not_found(self) -> None:
        response = MagicMock(spec=httpx.Response)
        response.status_code = 404
        with pytest.raises(RuntimeError, match="not found"):
            _check_response(response, "test resource")

    def test_rate_limited(self) -> None:
        response = MagicMock(spec=httpx.Response)
        response.status_code = 403
        response.headers = {"X-RateLimit-Remaining": "0"}
        with pytest.raises(RuntimeError, match="Rate limited"):
            _check_response(response, "test resource")

    def test_forbidden_non_rate_limit(self) -> None:
        response = MagicMock(spec=httpx.Response)
        response.status_code = 403
        response.headers = {"X-RateLimit-Remaining": "10"}
        with pytest.raises(RuntimeError, match="Access forbidden"):
            _check_response(response, "test resource")

    def test_unauthorized(self) -> None:
        response = MagicMock(spec=httpx.Response)
        response.status_code = 401
        with pytest.raises(RuntimeError, match="authentication failed"):
            _check_response(response, "test resource")

    def test_other_error(self) -> None:
        response = MagicMock(spec=httpx.Response)
        response.status_code = 500
        response.text = "Internal Server Error"
        with pytest.raises(RuntimeError, match="500"):
            _check_response(response, "test resource")


class TestFetchRepoInfo:
    """Tests for fetch_repo_info function."""

    def test_success(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "repo", "description": "Test repo"}
        mock_client.get.return_value = mock_response

        result = fetch_repo_info(mock_client, "owner", "repo")

        assert result["name"] == "repo"
        mock_client.get.assert_called_once()

    def test_not_found(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_client.get.return_value = mock_response

        with pytest.raises(RuntimeError, match="Repository not found"):
            fetch_repo_info(mock_client, "owner", "nonexistent")


class TestFetchRelease:
    """Tests for fetch_release function."""

    def test_latest_release(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"tag_name": "v1.0.0", "assets": []}
        mock_client.get.return_value = mock_response

        result = fetch_release(mock_client, "owner", "repo")

        assert result["tag_name"] == "v1.0.0"
        call_args = mock_client.get.call_args[0][0]
        assert "latest" in call_args

    def test_specific_version(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"tag_name": "v2.0.0", "assets": []}
        mock_client.get.return_value = mock_response

        result = fetch_release(mock_client, "owner", "repo", version="v2.0.0")

        assert result["tag_name"] == "v2.0.0"
        call_args = mock_client.get.call_args[0][0]
        assert "tags/v2.0.0" in call_args

    def test_include_pr(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"tag_name": "v1.0.0-beta", "assets": []}]
        mock_client.get.return_value = mock_response

        result = fetch_release(mock_client, "owner", "repo", include_pr=True)

        assert result["tag_name"] == "v1.0.0-beta"
        call_args = mock_client.get.call_args[0][0]
        assert "releases" in call_args
        assert "latest" not in call_args

    def test_no_releases(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_client.get.return_value = mock_response

        with pytest.raises(RuntimeError, match="No releases found"):
            fetch_release(mock_client, "owner", "repo", include_pr=True)


class TestDownloadAssetForHash:
    """Tests for download_asset_for_hash function."""

    def test_returns_sha256(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.content = b"test content"
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        import hashlib

        expected = hashlib.sha256(b"test content").hexdigest()
        result = download_asset_for_hash(mock_client, "https://example.com/file.zip")

        assert result == expected
