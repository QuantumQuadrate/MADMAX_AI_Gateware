from __future__ import annotations

from pathlib import Path

from .config import ExperimentConfig
from .paths import DEFAULT_GENERATED_DIR, resolve_workspace_path


def write_entangler_settings(cfg: ExperimentConfig, output: str | Path | None = None) -> Path:
    output_path = resolve_workspace_path(output) if output else DEFAULT_GENERATED_DIR / "entangler_settings.toml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_entangler_settings(cfg), encoding="utf-8")
    return output_path


def render_entangler_settings(cfg: ExperimentConfig) -> str:
    return f"""# Generated from MADMAX AI Gateware experiment config.
# This file is consumed by madmax-artiq-zynq's Nix dev shell.

NUM_OUTPUT_CHANNELS = {cfg.entangler.num_outputs}
NUM_ENTANGLER_INPUT_SIGNALS = {cfg.entangler.num_inputs}
NUM_GENERIC_INPUT_SIGNALS = {cfg.entangler.num_generic_inputs}
NUM_PATTERNS_ALLOWED = {cfg.entangler.num_patterns_allowed}

COARSE_COUNTER_WIDTH = 11
FULL_COUNTER_WIDTH = 14
MAX_CYCLES_PER_RUN = 16383
MAX_TRIGGER_COUNTS = 16383
"""

