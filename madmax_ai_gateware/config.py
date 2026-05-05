from pydantic import BaseModel
from typing import List

class Experiment(BaseModel):
    name: str
    description: str

class Target(BaseModel):
    board: str
    artiq_version: int
    variant: str

class Repositories(BaseModel):
    entangler_core_path: str
    artiq_zynq_path: str

class Hardware(BaseModel):
    dio_eem: int
    input_pads: List[str]
    output_pads: List[str]

class Entangler(BaseModel):
    mode: str = "default"
    num_inputs: int
    num_outputs: int
    coincidence_window_mu: int
    timeout_mu: int
    fast_branch: bool

class Build(BaseModel):
    output_dir: str
    dry_run: bool
    command_template: str

class Config(BaseModel):
    experiment: Experiment
    target: Target
    repositories: Repositories
    hardware: Hardware
    entangler: Entangler
    build: Build