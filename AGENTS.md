# AGENTS.md — scoop-create

## Project Overview

Python CLI tool that generates Scoop app manifests from GitHub repository URLs. Built with `uv`, `typer`, `pydantic`, and `httpx`.

## Commands

### Setup
```bash
uv sync              # Install dependencies
```

### Run
```bash
uv run scoop-create <github-url>          # Run CLI
uv run scoop-create --help                # Show help
uv run scoop-create owner/repo -o ./out   # With options
uv run scoop-create --dry-run             # Print without writing
uv run scoop-create --interactive         # Interactive mode
uv run scoop-create --release v1.0.0      # Target specific release
uv run scoop-create --include-pr          # Include pre-releases
uv run scoop-create --no-verify           # Disable TLS verification
uv run scoop-create -t 30                 # Set HTTP timeout (seconds)
uv run scoop-create -c /path/to/config    # Use custom config
```

### Build
```bash
uv build              # Build distribution (hatchling backend)
```

### Test
```bash
uv run pytest tests/              # Run all tests
uv run pytest tests/test_file.py  # Run single file
uv run pytest tests/test_file.py::test_name  # Run single test
```

### Lint / Format
```bash
uv run ruff check src/            # Lint
uv run ruff format src/           # Format
```

### Type Check
```bash
uv run mypy src/                  # Type check
```

## Code Style

### Imports
- Standard library first, then third-party, then local (grouped with blank lines)
- Use `from module import X` for specific imports
- Avoid lazy imports inside functions unless there's a genuine circular dependency

### Formatting
- 4-space indentation, no tabs
- Max line length: ~88 chars (Black/Ruff default)
- Trailing commas in multi-line structures
- f-strings for string interpolation

### Types
- Use Python 3.10+ union syntax: `str | None` (not `Optional[str]`)
- Type hints on all function signatures and parameters
- Use `dict[str, Any]` for untyped dicts, `tuple[str, str]` for tuples
- Pydantic `BaseModel` for structured data (`Manifest`, `Architecture`)
- `@dataclass` for service-layer return types (`ManifestResult`)

### Naming
- `snake_case` for functions, variables, modules
- `PascalCase` for classes (`Manifest`, `Architecture`, `ManifestResult`)
- `UPPER_SNAKE_CASE` for constants (`GITHUB_API`, `DEFAULT_CONFIG`, `SCORE_NON_WINDOWS`)
- `cli_` prefix for CLI override params in `merge_config` (e.g., `cli_proxy`, `cli_output`)
- `_` prefix for private/internal helpers (e.g., `_handle_error`, `_check_response`)

### Error Handling
- Raise `ValueError` for invalid input (e.g., bad GitHub URL format)
- Raise `RuntimeError` for external failures (GitHub API errors, network issues)
- CLI layer catches exceptions, prints styled error via `_handle_error`, and calls `raise SystemExit(code)`
- Graceful fallbacks: config load failures are silently skipped (`continue`)

### Console Output
- Use `rich.console.Console` with styled strings: `[red]Error:[/red]`, `[cyan]...[/cyan]`, `[green]...[/green]`, `[yellow]...[/yellow]`, `[dim]...[/dim]`
- `console.print()` for output, `console.input()` for user prompts

### Architecture
- `cli.py` — Typer CLI entry point, argument parsing, console I/O only
- `service.py` — Business logic orchestration (`create_manifest`, `compute_asset_hash`)
- `config.py` — Config loading from JSON files, env vars, CLI merging
- `github.py` — GitHub API client (repo info, releases, asset download); accepts shared `httpx.Client`
- `manifest.py` — Pydantic models, manifest building, JSON generation, file I/O
- `utils.py` — HTTP client factory, URL parsing, asset ranking heuristic
- Priority: CLI args > config file > env vars (`GITHUB_TOKEN`, `HTTP_PROXY`, `HTTPS_PROXY`) > defaults

### HTTP Client Management
- `github.py` functions accept an `httpx.Client` parameter — they do NOT create or close clients
- `service.py` owns the client lifecycle via `with httpx.Client()` context managers
- `utils.get_http_client()` returns a client; caller must close it (use context manager)
- TLS verification defaults to `True`; disable via `--no-verify-tls` or config `verify_tls: false`

### Conventions
- Module-level docstrings required: `"""Description of module."""`
- Pydantic `model_dump(exclude_none=True)` for JSON serialization
- JSON output: `indent=4, ensure_ascii=False` with trailing newline
- Config file: `config.json`, searched in CWD then `~/.config/scoop-create/`
- Extract duplicated logic into helpers (e.g., `_get_output_path`, `_check_response`)
