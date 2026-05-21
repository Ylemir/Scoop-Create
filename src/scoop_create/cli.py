"""Typer CLI entry point for scoop-create.

Handles argument parsing, configuration loading, and console I/O.
Business logic is delegated to the service and interactive modules.
"""

import json
import logging
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.logging import RichHandler

from scoop_create import __version__
from scoop_create.config import load_config, merge_config
from scoop_create.interactive import (
    confirm_write,
    print_manifest_preview,
    run_interactive_mode,
)
from scoop_create.manifest import write_manifest
from scoop_create.service import ManifestResult, create_manifest, get_output_path

app = typer.Typer(
    name="scoop-create",
    help="Generate Scoop app manifests from GitHub repository URLs",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


def _version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"scoop-create {__version__}")
        raise typer.Exit()


def _hook_callback(value: bool) -> None:
    """Print scoop-create hook command."""
    if value:
        print(
            'function scoop { if ($args[0] -eq "create") { scoop-create.exe @($args | Select-Object -Skip 1) } else { scoop.ps1 @args } }'
        )
        raise typer.Exit()


def _handle_error(message: str) -> None:
    """Print an error message and exit with code 1."""
    console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(code=1)


def _print_result_summary(result: ManifestResult) -> None:
    """Print a brief summary of the auto-detected manifest result."""
    console.print(f"[cyan]Repository:[/cyan] {result.owner}/{result.repo}")
    console.print(f"[cyan]Version:[/cyan] {result.version}")
    console.print(f"[cyan]Asset:[/cyan] {result.asset_name}")


def _handle_dry_run(manifest_data: dict[str, Any], output_path: Path) -> None:
    """Print manifest in dry-run mode without writing to disk."""
    console.print(json.dumps(manifest_data, indent=4, ensure_ascii=False))
    console.print(
        f"\n[yellow]Dry-run mode: manifest not written to {output_path}.[/yellow]"
    )


def _validate_output_dir(output: str | None) -> None:
    if output is None:
        return
    if Path(output).suffix.lower() == ".json":
        _handle_error(
            "--output/-o expects an output directory, not a .json file path. "
            "Pass a folder path (e.g. -o ./bucket)."
        )


@app.command()
def main(
    github_url: str = typer.Argument(
        ..., help="GitHub repository URL (e.g. https://github.com/owner/repo)"
    ),
    output: str | None = typer.Option(
        None,
        "-o",
        "--output",
        help="Output directory path (overrides config output_dir)",
    ),
    proxy: str | None = typer.Option(
        None, "-p", "--proxy", help="Proxy URL (overrides config proxy and env vars)"
    ),
    interactive: bool = typer.Option(
        False, "-i", "--interactive", help="Enable interactive mode"
    ),
    include_pr: bool = typer.Option(False, "--include-pr", help="Include pre-releases"),
    release: str | None = typer.Option(
        None, "-r", "--release", help="Specify release version/tag"
    ),
    dry_run: bool = typer.Option(
        False, "-n", "--dry-run", help="Print manifest without writing to disk"
    ),
    verify: bool = typer.Option(
        True, "--verify/--no-verify", help="Enable/disable TLS verification"
    ),
    timeout: float = typer.Option(
        20.0, "-t", "--timeout", help="HTTP request timeout in seconds"
    ),
    config_file: Path | None = typer.Option(
        None, "-c", "--config", help="Path to config file (default: config.json)"
    ),
    debug: bool = typer.Option(False, "-d", "--debug", help="Enable debug output"),
    version: Annotated[
        bool | None,
        typer.Option(
            "-v",
            "--version",
            help="Show version and exit",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
    hook: Annotated[
        bool | None,
        typer.Option(
            "--hook",
            help="Print PowerShell hook to replace `scoop create`",
            callback=_hook_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Generate a Scoop app manifest from a GitHub repository."""
    try:
        _validate_output_dir(output)
        config = load_config(config_file)
        config = merge_config(
            config,
            cli_proxy=proxy,
            cli_output=output,
            cli_interactive=interactive,
            cli_include_pr=include_pr,
            cli_verify=verify,
            cli_timeout=timeout,
            cli_debug=debug,
        )

        if config.debug:
            rich_handler = RichHandler(
                rich_tracebacks=False,
                show_path=False,
                markup=True,
                show_time=True,
                omit_repeated_times=False,
                keywords=[],
            )
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.DEBUG)
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            root_logger.addHandler(rich_handler)
            logging.getLogger("httpcore").setLevel(logging.WARNING)
            logging.getLogger("httpx").setLevel(logging.WARNING)
            console.print("[yellow]Debug mode enabled[/yellow]\n")

        result = create_manifest(github_url, config, version=release)
    except (ValueError, RuntimeError, OSError) as e:
        _handle_error(str(e))

    if not config.debug:
        _print_result_summary(result)

    if config.interactive:
        try:
            result = run_interactive_mode(result, config)
        except RuntimeError as e:
            _handle_error(str(e))
        print_manifest_preview(result.manifest_data)
        if not confirm_write():
            raise typer.Abort()

    output_path = get_output_path(config, result.repo)

    if dry_run:
        _handle_dry_run(result.manifest_data, output_path)
        return

    try:
        write_manifest(result.manifest_data, output_path)
    except OSError as e:
        _handle_error(f"Failed to write manifest: {e}")
    console.print(f"\n[green]Manifest written to:[/green] {output_path}")


if __name__ == "__main__":
    app()
