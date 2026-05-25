from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from .config import ExperimentConfig, load_config


def validate_config(cfg: ExperimentConfig, *, require_submodules: bool = False) -> list[str]:
    errors: list[str] = []

    for name, path in cfg.repositories.paths().items():
        if require_submodules and not path.exists():
            errors.append(f"{name} does not exist: {path}")

    if cfg.target.board != "kasli_soc":
        errors.append(f"unsupported target.board {cfg.target.board!r}; this workspace currently targets kasli_soc")

    if not cfg.entangler.ttl_bypass.required:
        errors.append("entangler.ttl_bypass.required must stay true for custom TTL-owning gateware")
    if cfg.entangler.ttl_bypass.software_setting != "enable":
        errors.append("entangler.ttl_bypass.software_setting must be 'enable' so software can disable custom TTL logic")
    if cfg.entangler.ttl_bypass.disabled_value != 0:
        errors.append("entangler.ttl_bypass.disabled_value must be 0 so enable=0 means normal TTL passthrough")

    input_indices = [_pin_index(pin) for pin in cfg.hardware.input_pads]
    output_indices = [_pin_index(pin) for pin in cfg.hardware.output_pads]
    if input_indices and output_indices and max(input_indices) >= min(output_indices):
        errors.append("expected DIO mapping with input pads before output pads")

    if _uses_atom_photon_parity(cfg):
        input_side_channels = cfg.entangler.num_inputs + cfg.entangler.num_generic_inputs
        if input_side_channels < 4:
            errors.append(
                "atom_photon_parity gateware must expose all four input-side DIO channels; "
                "set entangler.num_generic_inputs so num_inputs + num_generic_inputs >= 4"
            )
        if cfg.entangler.num_outputs < 4:
            errors.append("atom_photon_parity gateware must expose all four output-side DIO channels")

    return errors


def load_and_validate(path: str | Path, *, require_submodules: bool = False) -> tuple[ExperimentConfig | None, list[str]]:
    try:
        cfg = load_config(path)
    except ValidationError as exc:
        return None, [str(exc)]
    except Exception as exc:
        return None, [f"failed to load config: {exc}"]

    errors = validate_config(cfg, require_submodules=require_submodules)
    return cfg, errors


def _pin_index(pin: str) -> int:
    return int(pin.removeprefix("dio"))


def _uses_atom_photon_parity(cfg: ExperimentConfig) -> bool:
    return (
        cfg.target.variant == "atom_photon_parity_6"
        or cfg.experiment.name.startswith("atom_photon_parity")
        or cfg.repositories.entangler_core_branch
        in {"feature/atom-photon-parity", "feature/atom-photon-parity-gateware-redesign"}
    )
