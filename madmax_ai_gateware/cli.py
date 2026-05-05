import typer
from rich import print
import pathlib
from .validate import load_config, validate_config
from .submodules import check_submodules, init_submodules
from . import generate_settings as gs
from . import generate_device_db as gdb
from . import generate_experiment as ge
from . import build_gateware as bg
from .paths import WORKSPACE_ROOT

app = typer.Typer()

@app.command()
def setup():
    """Check if uv is installed and submodules are ready."""
    try:
        import subprocess
        subprocess.run(["uv", "--version"], check=True, capture_output=True)
        print("[green]uv is installed.[/green]")
    except:
        print("[red]uv is not installed. Please install uv: https://github.com/astral-sh/uv[/red]")
        return

    issues = check_submodules()
    if issues:
        print("[red]Submodule issues:[/red]")
        for issue in issues:
            print(f"  - {issue}")
        print("Run 'madmax submodules init' to fix.")
    else:
        print("[green]Submodules are ready.[/green]")

@app.command()
def submodules_init():
    """Initialize git submodules."""
    try:
        init_submodules()
        print("[green]Submodules initialized.[/green]")
    except Exception as e:
        print(f"[red]Failed to initialize submodules: {e}[/red]")

@app.command()
def validate(config_file: pathlib.Path = typer.Option(..., "--config", help="Path to experiment config YAML")):
    """Validate an experiment config."""
    try:
        cfg = load_config(config_file)
        errors = validate_config(cfg)
        if errors:
            print("[red]Validation errors:[/red]")
            for error in errors:
                print(f"  - {error}")
        else:
            print("[green]Config is valid.[/green]")
    except Exception as e:
        print(f"[red]Failed to validate config: {e}[/red]")

@app.command()
def generate_settings(config_file: pathlib.Path = typer.Option(..., "--config"), output: pathlib.Path = None):
    """Generate settings.toml from config."""
    cfg = load_config(config_file)
    gs.generate_settings(cfg, output)
    print(f"[green]Settings generated at {output or 'build/generated/settings.toml'}[/green]")

@app.command()
def generate_device_db(config_file: pathlib.Path = typer.Option(..., "--config"), output: pathlib.Path = None):
    """Generate device_db.py from config."""
    cfg = load_config(config_file)
    gdb.generate_device_db(cfg, output)
    print(f"[green]Device DB generated at {output or 'build/generated/device_db.py'}[/green]")

@app.command()
def generate_experiment(config_file: pathlib.Path = typer.Option(..., "--config"), output: pathlib.Path = None):
    """Generate test experiment from config."""
    cfg = load_config(config_file)
    ge.generate_experiment(cfg, output)
    print(f"[green]Experiment generated at {output or f'build/generated/experiments/{cfg.experiment.name}_test.py'}[/green]")

@app.command()
def build_gateware(config_file: pathlib.Path = typer.Option(..., "--config"), dry_run: bool = True):
    """Build gateware."""
    cfg = load_config(config_file)
    bg.build_gateware(cfg, dry_run)