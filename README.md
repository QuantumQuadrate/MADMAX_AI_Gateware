# MADMAX-AI-Gateware

This repository provides a reproducible AI-assisted workspace for MADMAX Kasli-SoC gateware development. It orchestrates two existing repositories as git submodules:

1. `madmax-entangler-core` - Contains the custom Migen/Entangler gateware logic.
2. `madmax-artiq-zynq` - Contains the ARTIQ/Kasli-SoC gateware build flow.

This new repository acts as the integration, automation, and AI-pipeline layer.

## Features

- Pull both repositories as git submodules.
- Create a Python environment using `uv`.
- Provide scripts for setup, validation, gateware build, runtime/device_db generation, and test experiment generation.
- Support for an AI pipeline where a user describes the desired experiment, and the system modifies the right files, builds the gateware, and writes matching ARTIQ test experiments.

## Installation

1. Ensure `uv` is installed: https://github.com/astral-sh/uv
2. Clone this repository: `git clone https://github.com/your-org/MADMAX-AI-Gateware.git`
3. Initialize submodules: `./scripts/init_submodules.sh`
4. Install Python dependencies: `uv sync`

## Usage

### Setup

Run `madmax setup` to check if everything is ready.

### Initialize Submodules

Run `madmax submodules init` or `./scripts/init_submodules.sh`.

### Validate Experiment Config

`madmax validate --config configs/experiments/2in_2out.yaml`

### Generate Settings

`madmax generate-settings --config configs/experiments/2in_2out.yaml`

### Generate Device DB

`madmax generate-device-db --config configs/experiments/2in_2out.yaml`

### Generate Experiment

`madmax generate-experiment --config configs/experiments/2in_2out.yaml`

### Build Gateware

`madmax build-gateware --config configs/experiments/2in_2out.yaml --dry-run`

## AI Pipeline

The future AI pipeline will work as follows:

1. User describes the desired experiment in natural language.
2. AI modifies the high-level YAML config in `configs/experiments/`.
3. AI validates the config.
4. AI generates settings, device_db, and test experiments.
5. AI builds gateware.
6. AI suggests testing the generated experiment.
7. Only then suggests flashing hardware.

The AI should avoid directly editing generated files and keep everything consistent.

## Repository Structure

- `repos/` - Git submodules for the integrated repositories.
- `configs/` - Experiment configurations, schemas, and templates.
- `madmax_ai_gateware/` - Python package for the tooling.
- `scripts/` - Shell scripts for automation.
- `ai/` - AI-related documentation and examples.
- `tests/` - Pytest tests.