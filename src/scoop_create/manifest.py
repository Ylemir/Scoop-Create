"""Manifest model and generation for Scoop app manifests."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class Architecture(BaseModel):
    """Architecture-specific URL and hash configuration."""

    url: str
    hash: str


APP_TYPE_CLI = "cli"
APP_TYPE_GUI = "gui"
APP_TYPE_BOTH = "both"


class Manifest(BaseModel):
    """Scoop app manifest model."""

    version: str
    description: str
    homepage: str
    license: str = "Unknown"
    bin: str | list[list[str]] | None = None
    shortcuts: list[list[str]] | None = None
    architecture: dict[str, Architecture] = {}
    checkver: dict[str, str] = {}
    autoupdate: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary, excluding None values."""
        return self.model_dump(exclude_none=True)

    def to_json(self) -> str:
        """Convert manifest to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=4, ensure_ascii=False)


@dataclass
class BinResult:
    """Result of bin/shortcuts field building."""

    bin: str | list[list[str]] | None
    shortcuts: list[list[str]] | None


def _build_bin_field(
    app_name: str, asset_name: str, app_type: str = APP_TYPE_BOTH
) -> BinResult:
    """Build the `bin` and `shortcuts` fields for the manifest based on app type.

    Args:
        app_name: The name of the application.
        asset_name: The name of the downloaded asset.
        app_type: The type of application ("cli", "gui", or "both").
                  Defaults to "both" for backward compatibility.

    Returns:
        BinResult: Contains the `bin` and `shortcuts` configurations.
    """
    bin_name = f"{app_name}.exe"

    if app_type == APP_TYPE_CLI:
        if bin_name == asset_name:
            return BinResult(bin=bin_name, shortcuts=None)
        if asset_name.endswith(".exe"):
            return BinResult(bin=[[asset_name, app_name]], shortcuts=None)
        return BinResult(bin=[[bin_name, app_name]], shortcuts=None)

    if asset_name.endswith(".exe"):
        bin_name = asset_name

    if app_type == APP_TYPE_GUI:
        return BinResult(bin=None, shortcuts=[[bin_name, app_name]])

    return BinResult(
        bin=[[bin_name, app_name]],
        shortcuts=[[bin_name, app_name]],
    )


def _build_autoupdate_url(asset_url: str, version: str) -> str:
    """Replace all occurrences of the version string with Scoop's $version placeholder.

    This allows Scoop to automatically update the URL when a new version is released.
    """
    return asset_url.replace(version, "$version")


@dataclass
class ManifestInput:
    """Input parameters for building a manifest."""

    version: str
    description: str
    homepage: str
    license_str: str
    asset_url: str
    asset_hash: str
    asset_name: str
    owner: str
    repo: str
    app_name: str
    app_type: str = APP_TYPE_BOTH


def build_manifest(input: ManifestInput) -> Manifest:
    """Build a Scoop manifest from structured input."""
    bin_result = _build_bin_field(input.app_name, input.asset_name, input.app_type)
    autoupdate_url = _build_autoupdate_url(input.asset_url, input.version)

    return Manifest(
        version=input.version,
        description=input.description,
        homepage=input.homepage,
        license=input.license_str or "Unknown",
        bin=bin_result.bin,
        shortcuts=bin_result.shortcuts,
        architecture={
            "64bit": Architecture(url=input.asset_url, hash=input.asset_hash)
        },
        checkver={"github": f"https://github.com/{input.owner}/{input.repo}"},
        autoupdate={
            "architecture": {
                "64bit": {
                    "url": autoupdate_url,
                }
            }
        },
    )


def merge_manifest(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge a new manifest dict into an existing one."""
    merged = dict(existing)
    for key, value in new.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = merge_manifest(merged[key], value)
        else:
            merged[key] = value
    return merged


def _remove_nested_field(data: dict[str, Any], path: str) -> None:
    parts = [p for p in path.split(".") if p]
    if not parts:
        return

    cur: Any = data
    for part in parts[:-1]:
        if not isinstance(cur, dict):
            return
        if part not in cur:
            return
        cur = cur[part]

    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def load_existing_manifest(path: Path) -> dict[str, Any] | None:
    """Load an existing manifest JSON file, returning None if missing or invalid."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        return None


def prepare_manifest_data(
    manifest: Manifest,
    merge: bool = True,
    output_path: Path | None = None,
    ignore_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Convert manifest to dict, optionally merging with an existing file."""
    new_data = manifest.to_dict()

    if ignore_fields:
        for field_path in ignore_fields:
            _remove_nested_field(new_data, field_path)

    if merge and output_path is not None:
        existing = load_existing_manifest(output_path)
        if existing is not None:
            new_data = merge_manifest(existing, new_data)

    return new_data


def write_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    """Write manifest dict to a JSON file with trailing newline."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4, ensure_ascii=False)
        f.write("\n")
