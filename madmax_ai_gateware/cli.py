from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console

from . import build_gateware as bg
from . import generate_device_db as gdb
from . import generate_experiment as ge
from . import generate_settings as gs
from .config import load_config
from .paths import DEFAULT_CONFIG, display_path
from .submodules import check_submodules, init_submodules
from .validate import load_and_validate, validate_config

console = Console()
app = typer.Typer(help="MADMAX AI-assisted gateware workspace tooling.")
submodules_app = typer.Typer(help="Manage external repository submodules.")
app.add_typer(submodules_app, name="submodules")


def _config_option() -> Path:
    return typer.Option(DEFAULT_CONFIG, "--config", "-c", help="Experiment YAML config.")


@app.command()
def setup() -> None:
    """Check uv and submodule readiness."""
    if shutil.which("uv"):
        console.print("[green]uv is installed.[/green]")
    else:
        console.print("[red]uv is not installed.[/red]")
        console.print("Install uv, then run: [bold]uv sync[/bold]")

    issues = check_submodules()
    if issues:
        console.print("[yellow]Submodule setup is incomplete:[/yellow]")
        for issue in issues:
            console.print(f"  - {issue}")
        console.print("Run: [bold]uv run madmax submodules init[/bold]")
    else:
        console.print("[green]Submodules are initialized.[/green]")


@submodules_app.command("init")
def submodules_init() -> None:
    """Initialize or update git submodules recursively."""
    result = init_submodules()
    if result.stdout.strip():
        console.print(result.stdout.strip())
    if result.stderr.strip():
        console.print(result.stderr.strip())
    console.print("[green]Submodules initialized.[/green]")


@app.command("validate")
def validate_command(
    config: Path = _config_option(),
    require_submodules: bool = typer.Option(False, "--require-submodules", help="Require submodule directories to exist."),
) -> None:
    """Validate an experiment config."""
    cfg, errors = load_and_validate(config, require_submodules=require_submodules)
    if errors:
        console.print("[red]Validation failed:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)
    assert cfg is not None
    console.print(f"[green]Config is valid:[/green] {display_path(config)}")


@app.command("generate-settings")
def generate_settings_command(
    config: Path = _config_option(),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output settings.toml path."),
) -> None:
    """Generate settings.toml from the experiment config."""
    cfg = _load_valid_config(config)
    path = gs.generate_settings(cfg, output)
    console.print(f"[green]Generated settings:[/green] {display_path(path)}")


@app.command("generate-device-db")
def generate_device_db_command(
    config: Path = _config_option(),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output device_db.py path."),
    core_host: str = typer.Option("192.168.1.75", "--core-host", help="Kasli-SoC core host for device_db.py."),
) -> None:
    """Generate a matching ARTIQ device_db.py."""
    cfg = _load_valid_config(config)
    path = gdb.generate_device_db(cfg, output, core_host=core_host)
    console.print(f"[green]Generated device DB:[/green] {display_path(path)}")


@app.command("generate-experiment")
def generate_experiment_command(
    config: Path = _config_option(),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file or directory."),
) -> None:
    """Generate a simple ARTIQ smoke-test experiment."""
    cfg = _load_valid_config(config)
    path = ge.generate_experiment(cfg, output)
    console.print(f"[green]Generated smoke experiment:[/green] {display_path(path)}")


@app.command("build-gateware")
def build_gateware_command(
    config: Path = _config_option(),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the build command instead of running it."),
) -> None:
    """Build or dry-run the Kasli-SoC gateware command."""
    cfg = _load_valid_config(config)
    effective_dry_run = dry_run or cfg.build.dry_run
    if effective_dry_run:
        for line in bg.dry_run_lines(cfg):
            console.print(line)
        return

    bg.build_gateware(cfg, dry_run=False)


def _load_valid_config(config: Path):
    cfg = load_config(config)
    errors = validate_config(cfg)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error:[/red] {error}")
        raise typer.Exit(1)
    return cfg


if __name__ == "__main__":
    app()

