"""Utilities: HTTP client factory, URL parsing, and asset ranking."""

import re
from typing import Any
from urllib.parse import urlparse

import httpx


def get_http_client(
    proxy: str = "",
    token: str = "",
    timeout: float = 20.0,
    verify: bool = True,
) -> httpx.Client:
    """Create an httpx.Client with the given configuration.

    The caller is responsible for closing the client (use a context manager).
    """
    headers = {"User-Agent": "scoop-create"}
    if token:
        headers["Authorization"] = f"token {token}"
    timeout_config = httpx.Timeout(timeout=timeout)
    kwargs: dict[str, Any] = {
        "headers": headers,
        "follow_redirects": True,
        "timeout": timeout_config,
        "verify": verify,
    }
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.Client(**kwargs)


def normalize_scoop_name(name: str) -> str:
    """Normalize a string to conform to Scoop manifest naming conventions.

    Scoop convention: lowercase, hyphens as separators, no underscores/spaces.
    """
    name = name.lower().strip()
    name = name.replace("_", "-").replace(" ", "-")
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    return name


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse a GitHub repository URL into (owner, repo).

    Accepts:
      - https://github.com/owner/repo
      - owner/repo
    """
    if "github.com" in url:
        parts = urlparse(url).path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
    elif "/" in url:
        owner, repo = url.strip().split("/", 1)
        return owner, repo.rstrip("/")

    raise ValueError(
        f"Invalid GitHub URL: {url}\n"
        "Accepted formats:\n"
        "  https://github.com/owner/repo\n"
        "  owner/repo"
    )


def guess_best_asset(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the best download asset from a release's asset list.

    Ranking criteria (lower is better):
      - Prefer Windows over non-Windows
      - Prefer x64/amd64 > x86 > generic > arm64
      - Prefer .zip/.7z > .exe > .tar.gz > other
      - Prefer portable builds
      - Exclude source code and non-Windows platform artifacts
    """
    if not assets:
        return None

    def asset_rank_key(asset: dict[str, Any]) -> tuple[int, int, int, int, str]:
        name = asset["name"].lower()

        if re.search(r"\.src|source|sources|src|darwin|linux|macos|android|ios", name):
            return (10, 0, 0, 0, name)

        win_score = 0 if re.search(r"win|windows", name) else 1

        arch_score = 5
        if re.search(r"x64|x86_64|x86-64|amd64|64bit", name):
            arch_score = 0
        elif re.search(r"x86|win32|ia32|32bit", name):
            arch_score = 1
        elif re.search(r"arm64", name):
            arch_score = 9

        type_score = 10
        if name.endswith((".zip", ".7z")):
            type_score = 0
        elif name.endswith(".exe"):
            type_score = 2
        elif name.endswith(".tar.gz"):
            type_score = 5

        port_score = 0 if re.search(r"portable|port", name) else 1

        return (win_score, arch_score, type_score, port_score, name)

    ranked = sorted(assets, key=asset_rank_key)
    return ranked[0]
