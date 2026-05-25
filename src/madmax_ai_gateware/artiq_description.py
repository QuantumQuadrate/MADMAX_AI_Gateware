from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import ExperimentConfig
from .paths import resolve_workspace_path


@dataclass(frozen=True)
class CardDefinition:
    type: str
    label: str
    port_count: int
    default_options: dict[str, Any] = field(default_factory=dict)
    requires_drtio: bool = False
    min_ports: int | None = None


CARD_DEFINITIONS: dict[str, CardDefinition] = {
    "dio": CardDefinition(
        "dio",
        "DIO",
        1,
        {
            "bank_direction_low": "input",
            "bank_direction_high": "output",
            "edge_counter": False,
        },
    ),
    "entangler": CardDefinition(
        "entangler",
        "Entangler",
        0,
        {"uses_reference": False, "running_output": False},
        min_ports=1,
    ),
    "urukul": CardDefinition(
        "urukul",
        "Urukul",
        2,
        {"dds": "ad9910", "clk_sel": 2, "synchronization": True},
    ),
    "zotino": CardDefinition("zotino", "Zotino", 1),
    "sampler": CardDefinition("sampler", "Sampler", 1),
    "mirny": CardDefinition("mirny", "Mirny", 1, {"clk_sel": 1, "refclk": 125e6}),
    "fastino": CardDefinition("fastino", "Fastino", 1),
    "grabber": CardDefinition("grabber", "Grabber", 1),
    "coaxpress_sfp": CardDefinition("coaxpress_sfp", "CoaXPress SFP", 0, {"roi_engine_count": 1}),
    "shuttler": CardDefinition("shuttler", "Shuttler", 1, requires_drtio=True),
    "phaser_drtio": CardDefinition("phaser_drtio", "Phaser DRTIO", 1, requires_drtio=True),
}


LEGACY_ENTANGLER_BRANCHES = {"", "master", "main", "artiq-integration"}


def logic_mode_for_branch(branch: str) -> str:
    branch_name = branch.strip()
    if branch_name.startswith("origin/"):
        branch_name = branch_name.removeprefix("origin/")
    if branch_name in LEGACY_ENTANGLER_BRANCHES:
        return "legacy"
    if branch_name.startswith("feature/"):
        branch_name = branch_name.removeprefix("feature/")
    if branch_name in {"atom-photon-parity", "atom-photon-parity-gateware-redesign"}:
        return "atom_photon_parity"
    return branch_name.replace("-", "_").replace("/", "_")


def entangler_default_options(cfg: ExperimentConfig) -> dict[str, Any]:
    options = {
        "uses_reference": False,
        "running_output": False,
    }
    logic_mode = logic_mode_for_branch(cfg.repositories.entangler_core_branch)
    if logic_mode != "legacy":
        options["logic_mode"] = logic_mode
    return options


def card_default_options(card_type: str, cfg: ExperimentConfig | None = None) -> dict[str, Any]:
    if card_type == "entangler" and cfg is not None:
        return entangler_default_options(cfg)
    definition = CARD_DEFINITIONS[card_type]
    return dict(definition.default_options)


def default_entangler_peripherals(cfg: ExperimentConfig) -> list[dict[str, Any]]:
    dio_peripheral = {
        "type": "dio",
        "ports": [cfg.hardware.dio_eem],
        "bank_direction_low": "input",
        "bank_direction_high": "output",
        "edge_counter": cfg.hardware.edge_counter,
    }
    entangler_peripheral = {
        "type": "entangler",
        "ports": [cfg.hardware.dio_eem],
        "overlay": True,
        **entangler_default_options(cfg),
    }
    return [dio_peripheral, entangler_peripheral]


def make_description(
    cfg: ExperimentConfig,
    peripherals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_peripherals = normalize_peripherals(
        peripherals if peripherals is not None else default_entangler_peripherals(cfg),
        cfg=cfg,
    )
    return {
        "target": cfg.target.board,
        "variant": cfg.target.variant,
        "hw_rev": cfg.target.hw_rev,
        "drtio_role": cfg.target.drtio_role,
        "rtio_frequency": cfg.target.rtio_frequency,
        "peripherals": normalized_peripherals,
    }


def write_artiq_description(
    cfg: ExperimentConfig,
    output: str | Path | None = None,
    peripherals: list[dict[str, Any]] | None = None,
) -> Path:
    output_path = resolve_workspace_path(output) if output else cfg.description_json_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    description = make_description(cfg, peripherals=peripherals)
    output_path.write_text(json.dumps(description, indent=4) + "\n", encoding="utf-8")
    return output_path


def normalize_peripherals(
    peripherals: list[dict[str, Any]],
    *,
    cfg: ExperimentConfig | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for peripheral in peripherals:
        card_type = peripheral.get("type")
        definition = CARD_DEFINITIONS.get(card_type)
        if definition is None:
            normalized.append(dict(peripheral))
            continue

        merged = {"type": card_type, **card_default_options(card_type, cfg)}
        if (definition.port_count != 0 or definition.min_ports is not None) and "ports" in peripheral:
            merged["ports"] = peripheral["ports"]
        for key, value in peripheral.items():
            if key != "type":
                merged[key] = value
        normalized.append(merged)
    return normalized


def validate_peripherals(peripherals: list[dict[str, Any]], *, drtio_role: str) -> list[str]:
    errors: list[str] = []
    used_ports: set[int] = set()
    dio_ports: set[int] = set()

    for index, peripheral in enumerate(normalize_peripherals(peripherals)):
        card_type = peripheral.get("type")
        definition = CARD_DEFINITIONS.get(card_type)
        if definition is None:
            errors.append(f"peripheral {index}: unsupported card type {card_type!r}")
            continue

        ports = peripheral.get("ports", [])
        if definition.min_ports is not None:
            if not isinstance(ports, list) or len(ports) < definition.min_ports:
                errors.append(f"peripheral {index} ({card_type}): expected at least {definition.min_ports} EEM port(s)")
                continue
            for port in ports:
                if not isinstance(port, int) or port < 0 or port > 11:
                    errors.append(f"peripheral {index} ({card_type}): invalid EEM port {port!r}")
                elif port in used_ports and not _allowed_entangler_overlap(card_type, port, dio_ports):
                    errors.append(f"peripheral {index} ({card_type}): EEM port {port} is already used")
                else:
                    used_ports.add(port)
                    if card_type == "dio":
                        dio_ports.add(port)
        elif definition.port_count == 0:
            if ports:
                errors.append(f"peripheral {index} ({card_type}): expected no EEM ports")
        else:
            if not isinstance(ports, list) or len(ports) != definition.port_count:
                errors.append(f"peripheral {index} ({card_type}): expected {definition.port_count} EEM port(s)")
                continue
            for port in ports:
                if not isinstance(port, int) or port < 0 or port > 11:
                    errors.append(f"peripheral {index} ({card_type}): invalid EEM port {port!r}")
                elif port in used_ports and not _allowed_entangler_overlap(card_type, port, dio_ports):
                    errors.append(f"peripheral {index} ({card_type}): EEM port {port} is already used")
                else:
                    used_ports.add(port)
                    if card_type == "dio":
                        dio_ports.add(port)

        if definition.requires_drtio and drtio_role == "standalone":
            errors.append(f"peripheral {index} ({card_type}) requires drtio_role master or satellite")

        if card_type == "dio":
            for key in ["bank_direction_low", "bank_direction_high"]:
                if peripheral.get(key) not in {"input", "output", "clkgen"}:
                    errors.append(f"peripheral {index} (dio): {key} must be input, output, or clkgen")

    return errors


def _allowed_entangler_overlap(card_type: str, port: int, dio_ports: set[int]) -> bool:
    return card_type == "entangler" and port in dio_ports
