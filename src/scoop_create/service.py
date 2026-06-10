"""Service layer: orchestrates manifest creation from GitHub repos."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scoop_create.config import AppConfig
from scoop_create.github import (
    download_asset_for_hash,
    fetch_release,
    fetch_repo_info,
)
from scoop_create.manifest import (
    APP_TYPE_BOTH,
    APP_TYPE_CLI,
    APP_TYPE_GUI,
    Manifest,
    ManifestInput,
    build_manifest,
    prepare_manifest_data,
)
from scoop_create.utils import (
    get_http_client,
    guess_best_asset,
    normalize_scoop_name,
    parse_github_url,
)

logger = logging.getLogger(__name__)


@dataclass
class ManifestResult:
    """Result of manifest creation, returned by the service layer."""

    owner: str
    repo: str
    app_name: str
    version: str
    description: str
    homepage: str
    license_str: str
    asset_name: str
    asset_url: str
    asset_hash: str
    manifest: Manifest
    manifest_data: dict[str, Any]
    app_type: str = APP_TYPE_BOTH


def _extract_http_config(config: AppConfig) -> dict[str, Any]:
    """Extract HTTP-related configuration from AppConfig."""
    return {
        "proxy": config.proxy,
        "token": config.github_token,
        "verify": config.verify,
        "timeout": config.timeout,
    }


def get_output_path(config: AppConfig, repo: str) -> Path:
    """Determine the output file path from config and repo name.

    The repo name is normalized to Scoop convention: lowercase, hyphens only.
    """
    name = normalize_scoop_name(repo)
    if config.output_dir:
        return Path(config.output_dir) / f"{name}.json"
    return Path(f"{name}.json")


def _download_and_hash_asset(url: str, http_config: dict[str, Any]) -> str:
    """Download an asset and compute its SHA256 hash."""
    with get_http_client(**http_config) as client:
        return download_asset_for_hash(client, url)


_GUI_ASSET_KEYWORDS = (
    "gui",
    "desktop",
    "setup",
    "installer",
    ".msi",
    "dmg",
    "appimage",
)
_CLI_ASSET_KEYWORDS = ("cli", "tui", "headless", "daemon", "server", "termux")


def infer_app_type(repo_info: dict[str, Any], assets: list[dict[str, Any]]) -> str:
    """Infer application type (cli, gui, or both) from repo metadata and assets.

    Args:
        repo_info: Repository information from GitHub API.
        assets: List of release assets.

    Returns:
        One of "cli", "gui", or "both".
    """
    topics = [t.lower() for t in (repo_info.get("topics") or [])]
    description = (repo_info.get("description", "") or "").lower()
    metadata = " ".join(topics) + " " + description

    gui_score = 0
    cli_score = 0

    for keyword in _GUI_ASSET_KEYWORDS:
        if keyword in metadata:
            gui_score += 2
        for asset in assets:
            if keyword in asset["name"].lower():
                gui_score += 1

    for keyword in _CLI_ASSET_KEYWORDS:
        if keyword in metadata:
            cli_score += 2
        for asset in assets:
            if keyword in asset["name"].lower():
                cli_score += 1

    if gui_score > 0 and cli_score == 0:
        return APP_TYPE_GUI
    if cli_score > 0 and gui_score == 0:
        return APP_TYPE_CLI
    return APP_TYPE_BOTH


def create_manifest(
    github_url: str,
    config: AppConfig,
    version: str | None = None,
) -> ManifestResult:
    """Orchestrate manifest creation from a GitHub repository URL.

    This is the core business logic, decoupled from CLI concerns.
    Manages a single httpx.Client for the entire operation.

    Args:
        github_url: GitHub repository URL (e.g. owner/repo or full URL).
        config: Merged configuration.
        version: Optional specific release tag.

    Returns:
        ManifestResult with all resolved values and the manifest data.

    Raises:
        ValueError: If the GitHub URL is invalid.
        RuntimeError: If GitHub API calls fail.
    """
    owner, repo = parse_github_url(github_url)
    # logger.debug("URL parsed | owner=%s repo=%s", owner, repo)
    http_config = _extract_http_config(config)

    with get_http_client(**http_config) as client:
        repo_info = fetch_repo_info(client, owner, repo)

        app_name = repo_info.get("name", repo)
        description = repo_info.get("description", "") or ""
        license_info = repo_info.get("license") or {}
        license_str = license_info.get("spdx_id", "") or license_info.get("name", "")
        homepage = repo_info.get("homepage") or f"https://github.com/{owner}/{repo}"

        release = fetch_release(
            client,
            owner,
            repo,
            version=version,
            include_pr=config.include_pr,
        )
        logger.debug(
            "Release fetched tag:[blue] %s [/blue]", release.get("tag_name", "unknown")
        )

    tag_name = release.get("tag_name", "")
    resolved_version = (version or tag_name).lstrip("v") or tag_name

    assets = release.get("assets", [])
    if config.debug:
        logger.debug(
            "Assets: %s",
            list(
                map(lambda a: f"{a['name']} - {a.get('size', 'unknown')}bytes", assets)
            ),
        )
    asset = guess_best_asset(assets)

    if asset is None:
        raise RuntimeError("No suitable release asset found.")

    logger.debug("Asset selected:[blue] %s [/blue]", asset["name"])
    asset_url = asset["browser_download_url"]
    asset_name = asset["name"]

    logger.debug("app description:[blue] %s [/blue]", repo_info.get("description"))
    logger.debug("topics: %s", repo_info.get("topics"))
    app_type = infer_app_type(repo_info, assets)
    logger.debug("App type inferred:[blue] %s [/blue]", app_type)

    asset_hash = asset.get("digest")
    if not asset_hash:
        logger.debug("Hash computation | downloading asset to compute SHA256")
        asset_hash = _download_and_hash_asset(asset_url, http_config)

    manifest = build_manifest(
        ManifestInput(
            version=resolved_version,
            description=description,
            homepage=homepage,
            license_str=license_str,
            asset_url=asset_url,
            asset_hash=asset_hash,
            asset_name=asset_name,
            owner=owner,
            repo=repo,
            app_name=app_name,
            app_type=app_type,
        )
    )

    output_path = get_output_path(config, repo)
    manifest_data = prepare_manifest_data(
        manifest,
        output_path=output_path,
        ignore_fields=config.ignore_manifest_fields,
    )

    return ManifestResult(
        owner=owner,
        repo=repo,
        app_name=app_name,
        version=resolved_version,
        description=description,
        homepage=homepage,
        license_str=license_str,
        asset_name=asset_name,
        asset_url=asset_url,
        asset_hash=asset_hash,
        manifest=manifest,
        manifest_data=manifest_data,
        app_type=app_type,
    )


def compute_asset_hash(
    asset_url: str,
    config: AppConfig,
) -> str:
    """Compute SHA256 hash for a single asset URL.

    Standalone function for interactive mode re-computation.
    """
    http_config = _extract_http_config(config)
    return _download_and_hash_asset(asset_url, http_config)
