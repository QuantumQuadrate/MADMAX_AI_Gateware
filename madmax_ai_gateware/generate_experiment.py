from __future__ import annotations

import re
from pathlib import Path

from .config import ExperimentConfig
from .paths import DEFAULT_GENERATED_DIR, resolve_workspace_path


def generate_experiment(cfg: ExperimentConfig, output: str | Path | None = None) -> Path:
    if output:
        output_path = resolve_workspace_path(output)
        if output_path.suffix != ".py":
            output_path = output_path / f"{_safe_name(cfg.experiment.name)}_smoke.py"
    else:
        output_path = DEFAULT_GENERATED_DIR / "experiments" / f"{_safe_name(cfg.experiment.name)}_smoke.py"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_experiment(cfg), encoding="utf-8")
    return output_path


def _render_experiment(cfg: ExperimentConfig) -> str:
    class_name = "".join(part.capitalize() for part in re.split(r"[^a-zA-Z0-9]+", cfg.experiment.name) if part)
    class_name = f"{class_name or 'Generated'}Smoke"
    if class_name[0].isdigit():
        class_name = f"Generated{class_name}"
    input_devices = [f"entangler_input{i}" for i in range(cfg.entangler.num_inputs)]
    output_devices = [f"entangler_output{i}" for i in range(cfg.entangler.num_outputs)]
    set_device_lines = "\n".join(f'        self.setattr_device("{name}")' for name in ["core", *input_devices, *output_devices, "entangler"])
    pulse_lines = "\n".join(
        f"        self.{name}.pulse(100 * ns)"
        for name in output_devices
    )
    input_comment = ", ".join(input_devices)

    return f'''# Generated smoke test for {cfg.experiment.name}.
# Source of truth: experiment YAML.

from artiq.experiment import EnvExperiment, kernel, ns


class {class_name}(EnvExperiment):
    def build(self):
{set_device_lines}

    @kernel
    def run(self):
        self.core.reset()
        # Input devices configured for basic presence checks: {input_comment}
{pulse_lines or "        pass"}
'''


def _safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower() or "generated"
