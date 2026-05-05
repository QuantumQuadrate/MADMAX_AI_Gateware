from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .paths import resolve_workspace_path

PIN_PATTERN = re.compile(r"^dio([0-7])$")


class Experiment(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class Target(BaseModel):
    board: str = Field(min_length=1)
    artiq_version: int = Field(ge=1)
    variant: str = Field(min_length=1)


class Repositories(BaseModel):
    artiq_env_path: str = "repos/madmax-artiq-env"
    entangler_core_path: str = "repos/madmax-entangler-core"
    artiq_zynq_path: str = "repos/madmax-artiq-zynq"

    def paths(self) -> dict[str, Path]:
        return {
            "artiq_env_path": resolve_workspace_path(self.artiq_env_path),
            "entangler_core_path": resolve_workspace_path(self.entangler_core_path),
            "artiq_zynq_path": resolve_workspace_path(self.artiq_zynq_path),
        }


class Hardware(BaseModel):
    dio_eem: int = Field(ge=0)
    input_pads: list[str] = Field(min_length=1)
    output_pads: list[str] = Field(min_length=1)

    @field_validator("input_pads", "output_pads")
    @classmethod
    def normalize_and_validate_pads(cls, pads: list[str]) -> list[str]:
        normalized = [pad.lower() for pad in pads]
        invalid = [pad for pad in normalized if not PIN_PATTERN.match(pad)]
        if invalid:
            raise ValueError(f"invalid DIO pad name(s): {', '.join(invalid)}; expected dio0 through dio7")
        if len(normalized) != len(set(normalized)):
            raise ValueError("pad lists cannot contain duplicates")
        return normalized

    @model_validator(mode="after")
    def validate_disjoint_pads(self) -> "Hardware":
        overlap = sorted(set(self.input_pads) & set(self.output_pads))
        if overlap:
            raise ValueError(f"input and output pads overlap: {', '.join(overlap)}")
        return self


class Entangler(BaseModel):
    num_inputs: int = Field(ge=1)
    num_outputs: int = Field(ge=1)
    coincidence_window_mu: int = Field(ge=1)
    timeout_mu: int = Field(ge=1)
    fast_branch: bool = True
    requested_goal: str = "low-latency branch decision"


class Build(BaseModel):
    output_dir: str = "build/generated"
    dry_run: bool = True
    command_template: str = Field(min_length=1)


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment: Experiment
    target: Target
    repositories: Repositories
    hardware: Hardware
    entangler: Entangler
    build: Build
    source_path: Path | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def validate_cross_references(self) -> "ExperimentConfig":
        if self.entangler.num_inputs != len(self.hardware.input_pads):
            raise ValueError(
                "entangler.num_inputs must match hardware.input_pads length "
                f"({self.entangler.num_inputs} != {len(self.hardware.input_pads)})"
            )
        if self.entangler.num_outputs != len(self.hardware.output_pads):
            raise ValueError(
                "entangler.num_outputs must match hardware.output_pads length "
                f"({self.entangler.num_outputs} != {len(self.hardware.output_pads)})"
            )
        return self

    @property
    def output_dir(self) -> Path:
        return resolve_workspace_path(self.build.output_dir)


def load_config(path: str | Path) -> ExperimentConfig:
    config_path = resolve_workspace_path(path)
    with config_path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh) or {}
    cfg = ExperimentConfig.model_validate(data)
    cfg.source_path = config_path
    return cfg

