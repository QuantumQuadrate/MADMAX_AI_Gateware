from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console

from . import artiq_description as ad
from . import artifacts
from . import build_gateware as bg
from . import generate_device_db as gdb
from . import generate_experiment as ge
from . import generate_settings as gs
from .config import load_config
from .entangler_core import checkout_entangler_branch
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


@app.command("generate-artiq-json")
def generate_artiq_json_command(
    config: Path = _config_option(),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output Kasli-SoC JSON description."),
) -> None:
    """Generate the Kasli-SoC JSON system description used by madmax-artiq-zynq."""
    cfg = _load_valid_config(config)
    path = ad.write_artiq_description(cfg, output)
    console.print(f"[green]Generated ARTIQ JSON description:[/green] {display_path(path)}")


@app.command("generate-artifact")
def generate_artifact_command(
    config: Path = _config_option(),
    output: Path | None = typer.Option(None, "--output", "-o", help="Artifact folder path."),
    core_host: str = typer.Option("192.168.1.75", "--core-host", help="Kasli-SoC core host for device_db.py."),
) -> None:
    """Create a reproducible artifact folder for the selected experiment and entangler branch."""
    cfg = _load_valid_config(config)
    path = artifacts.create_artifact_bundle(cfg, output=output, core_host=core_host)
    console.print(f"[green]Created artifact:[/green] {display_path(path)}")


@app.command("build-gateware")
def build_gateware_command(
    config: Path = _config_option(),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the build command instead of running it."),
    checkout_branch: bool = typer.Option(True, "--checkout-branch/--no-checkout-branch", help="Checkout repositories.entangler_core_branch before building."),
    artifact: bool = typer.Option(True, "--artifact/--no-artifact", help="Write a reproducibility artifact folder."),
) -> None:
    """Build or dry-run the Kasli-SoC gateware command."""
    cfg = _load_valid_config(config)
    if checkout_branch and not (dry_run or cfg.build.dry_run):
        checked_out = checkout_entangler_branch(
            cfg.repositories.entangler_core_branch,
            cfg.repositories.entangler_core_path,
        )
        console.print(f"[green]Using entangler-core branch:[/green] {checked_out}")
    build_inputs = artifacts.prepare_build_inputs(cfg)
    console.print(f"[green]Prepared JSON:[/green] {display_path(build_inputs['artiq_description_json'])}")
    console.print(f"[green]Prepared entangler settings:[/green] {display_path(build_inputs['entangler_settings'])}")
    if artifact and cfg.build.create_artifact:
        artifact_path = artifacts.create_artifact_bundle(cfg)
        console.print(f"[green]Created artifact:[/green] {display_path(artifact_path)}")

    effective_dry_run = dry_run or cfg.build.dry_run
    if effective_dry_run:
        for line in bg.dry_run_lines(cfg):
            console.print(line, markup=False)
        return

    bg.build_gateware(cfg, dry_run=False)


@app.command("gui")
def gui_command(config: Path = _config_option()) -> None:
    """Launch the Qt Kasli-SoC card mapping GUI."""
    from .gui import launch_gui

    try:
        launch_gui(config)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


@app.command("web-gui")
def web_gui_command(
    config: Path = _config_option(),
    host: str = typer.Option("127.0.0.1", "--host", help="HTTP host."),
    port: int = typer.Option(8765, "--port", help="HTTP port."),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open the browser automatically."),
) -> None:
    """Launch the browser-based card mapping GUI fallback."""
    from .web_gui import run_web_gui

    run_web_gui(config, host=host, port=port, open_browser=open_browser)


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
