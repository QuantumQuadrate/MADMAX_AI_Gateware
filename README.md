# MADMAX AI Gateware

`MADMAX-AI-Gateware` is the integration and automation layer for MADMAX Kasli-SoC gateware work. It does not copy gateware code from the underlying projects. Instead, it references them as Git submodules and provides deterministic tooling around a high-level experiment YAML file.

The core design rule is simple: an AI assistant should change the experiment config first, then Python tooling validates the request and generates the matching runtime files. Generated files are build artifacts, not the source of truth.

## Repositories

This workspace orchestrates:

- `repos/madmax-artiq-env`: Python/ARTIQ environment reference.
- `repos/madmax-artiq-zynq`: Kasli-SoC and ARTIQ Zynq gateware build flow.
- `repos/madmax-entangler-core`: custom Migen/Entangler logic.

## Setup

Install `uv`, then create the local environment:

```bash
uv sync
```

Initialize submodules:

```bash
./scripts/init_submodules.sh
# or
uv run madmax submodules init
```

Check the workspace:

```bash
uv run madmax setup
```

## Validate A Config

The example config lives at `configs/experiments/2in_2out.yaml`.

```bash
uv run madmax validate --config configs/experiments/2in_2out.yaml
```

Validation checks the schema, submodule-relative paths, entangler input/output counts, duplicate pads, and DIO pad names.

## Generate Runtime Files

Generate the settings file:

```bash
uv run madmax generate-settings --config configs/experiments/2in_2out.yaml
```

Generate the ARTIQ `device_db.py`:

```bash
uv run madmax generate-device-db --config configs/experiments/2in_2out.yaml
```

Generate a smoke-test experiment:

```bash
uv run madmax generate-experiment --config configs/experiments/2in_2out.yaml
```

By default, generated files are written under `build/generated/`.

## Gateware Build Dry Run

The initial implementation only performs dry-run build planning:

```bash
uv run madmax build-gateware --config configs/experiments/2in_2out.yaml --dry-run
```

The command is controlled by `build.command_template` in the YAML config. This keeps the ARTIQ/Kasli-SoC build details explicit and editable while the surrounding tooling remains stable.

## Scripts

- `scripts/setup.sh`: create/update the `uv` environment and print workspace status.
- `scripts/init_submodules.sh`: run `git submodule update --init --recursive`.
- `scripts/generate_runtime.sh`: validate and generate settings, `device_db.py`, and a smoke experiment.
- `scripts/build_gateware.sh`: dry-run the gateware build command.
- `scripts/smoke_test.sh`: run tests and a full generation dry run.

## Future AI Pipeline

The intended flow is:

1. A user describes the desired experiment.
2. The AI updates one high-level YAML config.
3. Deterministic validators reject inconsistent hardware, gateware, or runtime requests.
4. Generators write `settings.toml`, `device_db.py`, build descriptors, and smoke tests.
5. The build wrapper invokes `madmax-artiq-zynq`.
6. Tests run before any hardware flashing is suggested.

This keeps gateware, runtime configuration, and ARTIQ test experiments in sync without asking the AI to manually edit scattered files across multiple repositories.

