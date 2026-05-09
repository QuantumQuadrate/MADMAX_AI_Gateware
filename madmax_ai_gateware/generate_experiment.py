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
    if (
        cfg.target.variant in {"atom_photon_parity_6", "entangler_atom_photon"}
        or cfg.experiment.name.startswith("atom_photon_parity")
        or _is_atom_photon_parity_branch(cfg.repositories.entangler_core_branch)
    ):
        return _render_atom_photon_parity_experiment(cfg)

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
    patterns = [_pattern_bitfield(pattern.inputs) for pattern in cfg.entangler.patterns]
    pattern_comment = ", ".join(f"{pattern.name}=0b{_pattern_bitfield(pattern.inputs):0{cfg.entangler.num_inputs}b}" for pattern in cfg.entangler.patterns)

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
        # Entangler pattern logic: {pattern_comment or "no patterns configured"}
        self.entangler.set_patterns({patterns})
{pulse_lines or "        pass"}
'''


def _safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower() or "generated"


def _pattern_bitfield(inputs: list[int]) -> int:
    value = 0
    for index in inputs:
        value |= 1 << index
    return value


def _is_atom_photon_parity_branch(branch: str) -> bool:
    branch_name = branch.strip()
    if branch_name.startswith("origin/"):
        branch_name = branch_name.removeprefix("origin/")
    if branch_name.startswith("feature/"):
        branch_name = branch_name.removeprefix("feature/")
    return branch_name in {
        "atom-photon-parity",
        "atom-photon-parity-gateware-redesign",
    }


def _render_atom_photon_parity_experiment(cfg: ExperimentConfig) -> str:
    class_name = "".join(
        part.capitalize()
        for part in re.split(r"[^a-zA-Z0-9]+", cfg.experiment.name)
        if part
    )
    class_name = f"{class_name or 'AtomPhotonParity'}Smoke"
    if class_name[0].isdigit():
        class_name = f"Generated{class_name}"

    return f'''# Generated smoke test for {cfg.experiment.name}.
# Source of truth: experiment YAML.

from artiq.experiment import EnvExperiment, kernel


class {class_name}(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("entangler")

    @kernel
    def run(self):
        self.core.reset()
        self.entangler.clear()
        self.entangler.configure(True)
        self.entangler.set_run_length_mu(self.core.seconds_to_mu(50e-6))
        self.entangler.set_num_attempts(1)
        self.entangler.set_attempt_period_mu(self.core.seconds_to_mu(10e-6))
        self.entangler.set_gate_mu(self.core.seconds_to_mu(1e-6), self.core.seconds_to_mu(5e-6))
        # Safe smoke default: idle and active states match, so no output toggles.
        self.entangler.set_output_states(0, 0)
        self.entangler.set_branch_done_delay_mu(self.core.seconds_to_mu(5e-6))
        _, status = self.entangler.start()
        print(
            "atom_photon_parity",
            status,
            self.entangler.get_outcome(),
            self.entangler.get_click_timestamp_mu(),
        )
'''
