"""GitHub API client for fetching releases and assets.

All functions accept an httpx.Client parameter — the caller manages
the client lifecycle (typically via a context manager).
"""

import hashlib
import logging
from typing import Any

import httpx

from scoop_create.constants import GITHUB_API

logger = logging.getLogger(__name__)

__all__ = [
    "download_asset_for_hash",
    "fetch_release",
    "fetch_repo_info",
]


def _check_response(response: httpx.Response, context: str) -> None:
    """Raise RuntimeError with a descriptive message for non-200 responses.

    Args:
        response: HTTP response to check.
        context: Description of what was being fetched (for error messages).

    Raises:
        RuntimeError: If the response status code indicates an error.
    """
    if response.status_code == 200:
        return
    if response.status_code == 404:
        raise RuntimeError(f"{context} not found.")
    if response.status_code == 401:
        raise RuntimeError(
            "GitHub API authentication failed (401). Check your GITHUB_TOKEN or github_token in config."
        )
    if response.status_code == 403:
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        if remaining is not None and remaining.strip() == "0":
            details = ""
            if reset:
                details = f" (reset: {reset})"
            raise RuntimeError(
                "Rate limited by GitHub API (403). Set GITHUB_TOKEN or github_token in config."
                + details
            )
        raise RuntimeError(
            "Access forbidden by GitHub API (403). This may be due to missing permissions, an invalid token, or a blocked resource."
        )
    raise RuntimeError(f"Failed to {context} ({response.status_code}): {response.text}")


def fetch_repo_info(
    client: httpx.Client,
    owner: str,
    repo: str,
) -> dict[str, Any]:
    """Fetch repository metadata from GitHub API.

    Args:
        client: HTTP client with authentication configured.
        owner: GitHub repository owner.
        repo: GitHub repository name.

    Returns:
        Repository metadata as a dictionary.

    Raises:
        RuntimeError: If the repository is not found or API call fails.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    logger.debug("Fetching repo info:[blue] %s [/blue]", url)
    response = client.get(url)
    if response.status_code == 404:
        raise RuntimeError(f"Repository not found: {owner}/{repo}. Check the URL.")
    _check_response(response, "fetch repository info")
    return response.json()  # type: ignore[no-any-return]


def fetch_release(
    client: httpx.Client,
    owner: str,
    repo: str,
    version: str | None = None,
    include_pr: bool = False,
) -> dict[str, Any]:
    """Fetch a release from GitHub API.

    Args:
        client: HTTP client with authentication configured.
        owner: GitHub repository owner.
        repo: GitHub repository name.
        version: Specific tag to fetch. If None, fetches latest release.
        include_pr: If True and version is None, include pre-releases.

    Returns:
        Release data as a dictionary.

    Raises:
        RuntimeError: If no releases are found or API call fails.
    """
    api_base = f"{GITHUB_API}/repos/{owner}/{repo}/releases"

    if version:
        url = f"{api_base}/tags/{version}"
        logger.debug("Fetching release by tag:[blue] %s [/blue]", version)
        response = client.get(url)
        _check_response(response, "fetch release")
        return response.json()  # type: ignore[no-any-return]

    if include_pr:
        logger.debug("Fetching all releases include pre-releases")
        response = client.get(api_base)
        _check_response(response, "fetch releases")
        releases: list[dict[str, Any]] = response.json()
        if not releases:
            raise RuntimeError("No releases found.")
        logger.debug("Releases found count:[blue] %d [/blue]", len(releases))
        return releases[0]

    url = f"{api_base}/latest"
    logger.debug("Fetching latest release")
    response = client.get(url)
    _check_response(response, "fetch latest release")
    return response.json()  # type: ignore[no-any-return]


def download_asset_for_hash(
    client: httpx.Client,
    url: str,
) -> str:
    """Download an asset and return its SHA256 hex digest.

    Args:
        client: HTTP client for downloading the asset.
        url: Direct download URL of the asset.

    Returns:
        SHA256 hex digest of the asset content.

    Raises:
        httpx.HTTPStatusError: If the download fails.
    """
    logger.debug("Downloading asset:[blue] %s [/blue]", url)
    response = client.get(url)
    response.raise_for_status()
    content_size = len(response.content)
    logger.debug("Asset downloaded:[blue] %.2f KB [/blue]", content_size / 1024)
    return hashlib.sha256(response.content).hexdigest()
