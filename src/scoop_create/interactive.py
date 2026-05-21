"""Interactive mode for confirming and editing manifest fields."""

import json
from typing import Any

from prompt_toolkit import prompt
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.widgets import RadioList
from rich.console import Console

from scoop_create.config import AppConfig
from scoop_create.manifest import (
    APP_TYPE_BOTH,
    APP_TYPE_CLI,
    APP_TYPE_GUI,
    ManifestInput,
    build_manifest,
    prepare_manifest_data,
)
from scoop_create.service import ManifestResult, compute_asset_hash, get_output_path

console = Console()


def _prompt_confirm_field(
    field_name: str,
    current_value: str,
    required: bool = False,
) -> str:
    """Prompt user to confirm or edit a manifest field value.

    Args:
        field_name: Display name of the field.
        current_value: Current auto-detected value (pre-filled in input).
        required: If True, re-prompt until a non-empty value is provided.

    Returns:
        The confirmed (or edited) value.
    """
    console.print(f"[cyan]{field_name}:[/cyan]")
    while True:
        result = prompt(
            "  > ",
            default=current_value,
        ).strip()
        if result:
            return result
        if not required:
            return current_value
        console.print(
            f"  [yellow]{field_name} is required, please enter a value.[/yellow]"
        )


def run_interactive_mode(
    result: ManifestResult,
    config: AppConfig,
) -> ManifestResult:
    """Run interactive field confirmation/editing and return updated result.

    Args:
        result: Auto-detected manifest result.
        config: Application configuration.

    Returns:
        Updated ManifestResult with user-confirmed values.
    """
    console.print("\n[cyan]--- Confirm manifest fields ---[/cyan]\n")

    version = _prompt_confirm_field("version", result.version, required=True)
    description = _prompt_confirm_field("description", result.description)
    homepage = _prompt_confirm_field("homepage", result.homepage, required=True)
    license_str = _prompt_confirm_field("license", result.license_str or "Unknown")
    app_name = _prompt_confirm_field("app_name", result.app_name, required=True)

    console.print("\n[cyan]app_type:[/cyan]")
    app_type_choices = [
        (APP_TYPE_CLI, "cli     - Command-line application"),
        (APP_TYPE_GUI, "gui     - Graphical user interface application"),
        (APP_TYPE_BOTH, "both    - Both CLI and GUI support"),
    ]

    radio_list: RadioList[str] = RadioList(
        app_type_choices,
        default=result.app_type or APP_TYPE_BOTH,
        selected_style="bg:#005f5f #ffffff bold",
        checked_style="bg:#005f5f #ffffff bold",
        default_style="bold",
    )

    bindings = KeyBindings()

    @bindings.add("space", eager=True)
    def _select(event: Any) -> None:
        radio_list.current_value = radio_list.values[radio_list._selected_index][0]

    @bindings.add("enter", eager=True)
    def _accept(event: Any) -> None:
        radio_list.current_value = radio_list.values[radio_list._selected_index][0]
        event.app.exit(result=radio_list.current_value)

    console.print("[dim]Use ↑/↓ to navigate, Space to select, Enter to confirm[/dim]\n")
    app: Application[str] = Application(
        layout=Layout(radio_list), key_bindings=bindings, full_screen=False
    )
    app_type = app.run()
    console.print(f"  [green]Selected: {app_type}[/green]\n")

    asset_url = result.asset_url
    asset_name = result.asset_name
    asset_hash = result.asset_hash

    console.print(f"[cyan]asset_url:[/cyan] {asset_url}")
    asset_url_input = console.input(
        "  [dim]Press Enter to accept, or type new URL:[/dim] "
    ).strip()
    if asset_url_input:
        asset_url = asset_url_input
        asset_name = asset_url.rsplit("/", 1)[-1]
        console.print("[cyan]Recomputing SHA256 for new asset...[/cyan]")
        try:
            asset_hash = compute_asset_hash(asset_url, config)
        except Exception as e:
            console.print(f"[red]Error:[/red] Error downloading asset: {e}")
            raise RuntimeError(f"Error downloading asset: {e}") from e

    console.print(f"[cyan]hash:[/cyan] {asset_hash}")
    hash_confirm = console.input(
        "  [dim]Press Enter to accept, or type new hash:[/dim] "
    ).strip()
    if hash_confirm:
        asset_hash = hash_confirm
    console.print()

    manifest = build_manifest(
        ManifestInput(
            version=version,
            description=description,
            homepage=homepage,
            license_str=license_str,
            asset_url=asset_url,
            asset_hash=asset_hash,
            asset_name=asset_name,
            owner=result.owner,
            repo=result.repo,
            app_name=app_name,
            app_type=app_type,
        )
    )

    output_path = get_output_path(config, result.repo)
    manifest_data = prepare_manifest_data(
        manifest,
        output_path=output_path,
        ignore_fields=config.ignore_manifest_fields,
    )

    return ManifestResult(
        owner=result.owner,
        repo=result.repo,
        app_name=app_name,
        version=version,
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


def print_manifest_preview(manifest_data: dict[str, Any]) -> None:
    """Print a formatted preview of the manifest data."""
    console.print("\n[cyan]Generated manifest:[/cyan]")
    console.print(json.dumps(manifest_data, indent=4, ensure_ascii=False))


def confirm_write() -> bool:
    """Prompt user to confirm writing the manifest.

    Returns:
        True if user confirms, False otherwise.
    """
    confirm = console.input("\n[cyan]Write manifest? (y/n):[/cyan] ")
    return confirm.strip().lower() in ("y", "yes")
