from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .artiq_description import write_artiq_description
from .build_gateware import build_context, render_build_steps, render_build_command
from .config import ExperimentConfig
from .entangler_settings import write_entangler_settings
from .generate_device_db import generate_device_db
from .generate_experiment import generate_experiment
from .generate_settings import generate_settings
from .paths import display_path, resolve_workspace_path


def prepare_build_inputs(cfg: ExperimentConfig, *, peripherals: list[dict[str, Any]] | None = None) -> dict[str, Path]:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    return {
        "artiq_description_json": write_artiq_description(
            cfg,
            cfg.description_json_path,
            peripherals=peripherals,
        ),
        "settings": generate_settings(cfg, cfg.output_dir / "settings.toml"),
        "entangler_settings": write_entangler_settings(cfg, cfg.output_dir / "entangler_settings.toml"),
    }


def create_artifact_bundle(
    cfg: ExperimentConfig,
    *,
    peripherals: list[dict[str, Any]] | None = None,
    output: str | Path | None = None,
    core_host: str = "192.168.1.75",
) -> Path:
    artifact_dir = _artifact_path(cfg, output)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    generated = {
        "artiq_description_json": write_artiq_description(
            cfg,
            artifact_dir / f"{cfg.target.variant}.json",
            peripherals=peripherals,
        ),
        "settings": generate_settings(cfg, artifact_dir / "settings.toml"),
        "entangler_settings": write_entangler_settings(cfg, artifact_dir / "entangler_settings.toml"),
        "device_db": generate_device_db(cfg, artifact_dir / "device_db.py", core_host=core_host),
        "smoke_experiment": generate_experiment(cfg, artifact_dir / "repository"),
    }

    if cfg.source_path and cfg.source_path.exists():
        shutil.copy2(cfg.source_path, artifact_dir / "source_config.yaml")

    normalized_config = cfg.model_dump(mode="json", exclude={"source_path"})
    (artifact_dir / "experiment_config.normalized.json").write_text(
        json.dumps(normalized_config, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = _manifest(cfg, artifact_dir, generated)
    (artifact_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (artifact_dir / "README.md").write_text(_readme(cfg, manifest), encoding="utf-8")
    return artifact_dir


def _artifact_path(cfg: ExperimentConfig, output: str | Path | None) -> Path:
    if output is not None:
        return resolve_workspace_path(output)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    name = _safe_name(cfg.experiment.name)
    return cfg.artifact_dir / f"{name}-{stamp}"


def _manifest(cfg: ExperimentConfig, artifact_dir: Path, generated: dict[str, Path]) -> dict[str, Any]:
    repo_paths = cfg.repositories.paths()
    return {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "artifact_dir": display_path(artifact_dir),
        "experiment": cfg.experiment.name,
        "target": cfg.target.model_dump(mode="json"),
        "source_config": display_path(cfg.source_path) if cfg.source_path else None,
        "selected_entangler_core_branch": cfg.repositories.entangler_core_branch,
        "ttl_bypass": cfg.entangler.ttl_bypass.model_dump(mode="json"),
        "generated_files": {name: display_path(path) for name, path in generated.items()},
        "build_context": build_context(cfg),
        "build_steps": render_build_steps(cfg),
        "single_command": render_build_command(cfg),
        "repositories": {
            "artiq_env": _git_snapshot(repo_paths["artiq_env_path"]),
            "artiq_zynq": _git_snapshot(repo_paths["artiq_zynq_path"]),
            "entangler_core": _git_snapshot(
                repo_paths["entangler_core_path"],
                expected_branch=cfg.repositories.entangler_core_branch,
            ),
        },
    }


def _git_snapshot(path: Path, *, expected_branch: str | None = None) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "path": display_path(path),
        "exists": path.exists(),
        "expected_branch": expected_branch,
    }
    if not path.exists():
        return snapshot

    branch = _git(path, "branch", "--show-current")
    commit = _git(path, "rev-parse", "HEAD")
    snapshot.update(
        {
            "branch": branch or _git(path, "rev-parse", "--short", "HEAD"),
            "commit": commit,
            "short_commit": commit[:12] if commit else "",
            "dirty": bool(_git(path, "status", "--short")),
            "status": _git(path, "status", "--short").splitlines(),
            "remote": _git(path, "remote", "get-url", "origin"),
        }
    )
    snapshot["branch_matches_config"] = expected_branch in {None, "", snapshot["branch"]}
    return snapshot


def _git(path: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=path,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _readme(cfg: ExperimentConfig, manifest: dict[str, Any]) -> str:
    entangler_repo = manifest["repositories"]["entangler_core"]
    return f"""# Gateware Artifact: {cfg.experiment.name}

This folder records the generated inputs used for a MADMAX gateware build.

- Entangler core branch: `{cfg.repositories.entangler_core_branch}`
- Entangler core checkout: `{entangler_repo.get("branch", "")}` at `{entangler_repo.get("short_commit", "")}`
- Branch matches config: `{entangler_repo.get("branch_matches_config", False)}`
- ARTIQ target: `{cfg.target.board}` / `{cfg.target.variant}`
- Build role: `{cfg.target.drtio_role}`
- TTL bypass: `{cfg.entangler.ttl_bypass.software_setting}={cfg.entangler.ttl_bypass.disabled_value}` means `{cfg.entangler.ttl_bypass.behavior}`

Files in this artifact are copied or regenerated from the experiment config:

- `{cfg.target.variant}.json`: Kasli-SoC JSON description.
- `settings.toml`: runtime settings generated from the experiment config.
- `entangler_settings.toml`: compile-time entangler settings consumed by the Nix shell.
- `device_db.py`: generated ARTIQ device database.
- `repository/`: generated smoke-test experiment.
- `source_config.yaml` and `experiment_config.normalized.json`: the original and normalized source configuration.
- `manifest.json`: repository refs, dirty status, branch selection, and build commands.
"""


def _safe_name(name: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in name.strip().lower())
    safe = "_".join(part for part in safe.split("_") if part)
    return safe or "experiment"
