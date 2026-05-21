"""Configuration loading and validation for scoop-create."""

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Application configuration with validation."""

    proxy: str = ""
    output_dir: str = ""
    ignore_manifest_fields: list[str] = []
    include_pr: bool = False
    interactive: bool = False
    github_token: str = ""
    verify: bool = True
    timeout: float = Field(default=20.0, gt=0)
    debug: bool = False


def _find_config_paths(explicit_path: Path | None = None) -> list[Path]:
    """Return paths to config files that exist, in ascending priority order."""
    paths: list[Path] = []

    if explicit_path is not None:
        if explicit_path.exists():
            paths.append(explicit_path)
        return paths

    user_config = Path.home() / ".config" / "scoop-create" / "config.json"
    if user_config.exists():
        paths.append(user_config)

    local_config = Path.cwd() / "config.json"
    if local_config.exists():
        paths.append(local_config)

    return paths


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from JSON files, falling back to defaults."""
    data: dict[str, Any] = {}

    for config_file in _find_config_paths(config_path):
        with open(config_file, encoding="utf-8") as f:
            file_config = json.load(f)
        for key in AppConfig.model_fields:
            if key in file_config and file_config[key] is not None:
                data[key] = file_config[key]
    return AppConfig(**data)


def merge_config(
    config: AppConfig,
    cli_proxy: str | None = None,
    cli_output: str | None = None,
    cli_interactive: bool = False,
    cli_include_pr: bool = False,
    cli_verify: bool = True,
    cli_timeout: float | None = None,
    cli_debug: bool = False,
) -> AppConfig:
    """Merge config layers: defaults < file < env vars < CLI args."""
    merged = AppConfig(**config.model_dump())

    env_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY", "")
    env_token = os.environ.get("GITHUB_TOKEN", "")

    if not merged.proxy and env_proxy:
        merged.proxy = env_proxy

    if not merged.github_token and env_token:
        merged.github_token = env_token

    if cli_proxy:
        merged.proxy = cli_proxy

    if cli_output:
        merged.output_dir = cli_output

    if cli_interactive:
        merged.interactive = True

    if cli_include_pr:
        merged.include_pr = True

    merged.verify = cli_verify

    if cli_timeout is not None:
        merged.timeout = cli_timeout

    if cli_debug:
        merged.debug = True

    return merged
