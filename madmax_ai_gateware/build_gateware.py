from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from .config import ExperimentConfig
from .entangler_core import entangler_override_args
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


def firmware_name(cfg: ExperimentConfig) -> str:
    return "satman" if cfg.target.drtio_role == "satellite" else "runtime"


def render_build_steps(cfg: ExperimentConfig) -> list[str]:
    context = build_context(cfg)
    zynq = Path(context["artiq_zynq_path"])
    desc = shlex.quote(context["artiq_description_json"])
    firmware = firmware_name(cfg)
    override = " ".join(shlex.quote(arg) for arg in entangler_override_args())
    gateware_script = shlex.quote(f"cd src && python gateware/kasli_soc.py -g ../build/gateware {desc}")
    firmware_script = shlex.quote(f"cd src && make TARGET=kasli_soc GWARGS={desc} {shlex.quote(firmware)}")
    device_db_script = shlex.quote(f"python entangler_device_db_maker.py {desc} > device_db.py")
    return [
        f"cd {shlex.quote(str(zynq))} && nix develop {override} --command bash -lc {gateware_script}",
        f"cd {shlex.quote(str(zynq))} && nix develop {override} --command bash -lc {firmware_script}",
        f"mkdir -p {shlex.quote(str(zynq / 'build'))} && cd {shlex.quote(str(zynq / 'build'))} && nix build git+https://git.m-labs.hk/m-labs/zynq-rs#kasli_soc-szl",
        (
            f"cd {shlex.quote(str(zynq / 'build'))} && "
            "printf '%s\\n' 'the_ROM_image:' '{' '  [bootloader]result/szl.elf' "
            f"'  gateware/top.bit' '  firmware/armv7-none-eabihf/release/{firmware}' "
            f"'}}' > boot.bif && nix develop {override} .. --command mkbootimage boot.bif boot.bin"
        ),
        f"cd {shlex.quote(str(zynq))} && nix develop {override} --command bash -lc {device_db_script}",
    ]


def build_gateware(cfg: ExperimentConfig, *, dry_run: bool | None = None) -> subprocess.CompletedProcess[str] | str:
    effective_dry_run = cfg.build.dry_run if dry_run is None else dry_run
    command = render_build_command(cfg)
    if effective_dry_run:
        return command
    return subprocess.run(command, cwd=WORKSPACE_ROOT, shell=True, check=True, text=True)


def command_as_argv(command: str) -> list[str]:
    return shlex.split(command)


def dry_run_lines(cfg: ExperimentConfig) -> list[str]:
    lines = [
        "Dry-run gateware build plan:",
        f"  config: {display_path(cfg.source_path) if cfg.source_path else '<in-memory>'}",
        f"  output: {display_path(cfg.output_dir)}",
        f"  JSON description: {display_path(build_context(cfg)['artiq_description_json'])}",
    ]
    for index, step in enumerate(render_build_steps(cfg), start=1):
        lines.append(f"  {index}. {step}")
    lines.append(f"  configurable single command: {render_build_command(cfg)}")
    return lines
