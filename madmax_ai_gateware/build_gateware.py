from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from .config import ExperimentConfig
from .paths import WORKSPACE_ROOT, display_path, resolve_workspace_path


def build_context(cfg: ExperimentConfig) -> dict[str, str]:
    output_dir = cfg.output_dir
    context = {
        "workspace_root": str(WORKSPACE_ROOT),
        "artiq_env_path": str(resolve_workspace_path(cfg.repositories.artiq_env_path)),
        "artiq_zynq_path": str(resolve_workspace_path(cfg.repositories.artiq_zynq_path)),
        "entangler_core_path": str(resolve_workspace_path(cfg.repositories.entangler_core_path)),
        "board": cfg.target.board,
        "variant": cfg.target.variant,
        "artiq_version": str(cfg.target.artiq_version),
        "output_dir": str(output_dir),
        "gateware_build_dir": str(output_dir / "gateware"),
        "settings_path": str(output_dir / "settings.toml"),
        "device_db_path": str(output_dir / "device_db.py"),
        "artiq_description_json": str(output_dir / f"{cfg.target.variant}.json"),
    }
    return context


def render_build_command(cfg: ExperimentConfig) -> str:
    return cfg.build.command_template.format(**build_context(cfg))


def build_gateware(cfg: ExperimentConfig, *, dry_run: bool | None = None) -> subprocess.CompletedProcess[str] | str:
    effective_dry_run = cfg.build.dry_run if dry_run is None else dry_run
    command = render_build_command(cfg)
    if effective_dry_run:
        return command
    return subprocess.run(command, cwd=WORKSPACE_ROOT, shell=True, check=True, text=True)


def command_as_argv(command: str) -> list[str]:
    return shlex.split(command)


def dry_run_lines(cfg: ExperimentConfig) -> list[str]:
    command = render_build_command(cfg)
    return [
        "Dry-run gateware build plan:",
        f"  config: {display_path(cfg.source_path) if cfg.source_path else '<in-memory>'}",
        f"  output: {display_path(cfg.output_dir)}",
        f"  command: {command}",
    ]

