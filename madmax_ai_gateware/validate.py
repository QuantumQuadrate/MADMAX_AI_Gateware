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

    input_indices = [_pin_index(pin) for pin in cfg.hardware.input_pads]
    output_indices = [_pin_index(pin) for pin in cfg.hardware.output_pads]
    if input_indices and output_indices and max(input_indices) >= min(output_indices):
        errors.append("expected DIO mapping with input pads before output pads")

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

