from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ExperimentConfig
from .paths import DEFAULT_GENERATED_DIR, resolve_workspace_path


def build_artiq_description(cfg: ExperimentConfig) -> dict[str, Any]:
    return {
        "target": cfg.target.board,
        "variant": cfg.target.variant,
        "hw_rev": "v1.0",
        "drtio_role": "standalone",
        "rtio_frequency": 125e6,
        "enable_acpki": False,
        "enable_wrpll": False,
        "sed_lanes": 8,
        "peripherals": [
            {
                "type": "entangler",
                "ports": [cfg.hardware.dio_eem],
                "uses_reference": False,
                "running_output": False,
            }
        ],
    }


def generate_artiq_description(cfg: ExperimentConfig, output: str | Path | None = None) -> Path:
    output_path = (
        resolve_workspace_path(output)
        if output
        else DEFAULT_GENERATED_DIR / f"{cfg.target.variant}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_artiq_description(cfg), indent=4) + "\n",
        encoding="utf-8",
    )
    return output_path
