# MADMAX AI Gateware

`MADMAX-AI-Gateware` is the integration and automation layer for MADMAX Kasli-SoC gateware work. It does not copy gateware code from the underlying projects. Instead, it references them as Git submodules and provides deterministic tooling around a high-level experiment YAML file.

The core design rule is simple: an AI assistant should change the experiment config first, then Python tooling validates the request and generates the matching runtime files. Generated files are build artifacts, not the source of truth.

## Repositories

This workspace orchestrates:

- `repos/madmax-artiq-env`: Python/ARTIQ environment reference.
- `repos/madmax-artiq-zynq`: Kasli-SoC and ARTIQ Zynq gateware build flow.
- `repos/madmax-entangler-core`: custom Migen/Entangler logic.

## Documentation

- [Atom-photon parity 6 gateware helper](docs/atom_photon_parity_6_gateware.md):
  documents the current parity-6 helper contract, registers, timing model, and
  hardware test ladder.

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

Generate the Kasli-SoC JSON system description:

```bash
uv run madmax generate-artiq-json --config configs/experiments/2in_2out.yaml
```

By default, generated files are written under `build/generated/`.

## Gateware Build Dry Run

The initial implementation only performs dry-run build planning:

```bash
uv run madmax build-gateware --config configs/experiments/2in_2out.yaml --dry-run
```

The dry-run prints the end-to-end `madmax-artiq-zynq` flow:

1. Build `build/gateware/top.bit` from the generated JSON description.
2. Build matching firmware, `runtime.bin` for `standalone`/`master` or `satman.bin` for `satellite`.
3. Build the Kasli-SoC second-stage bootloader.
4. Package `build/boot.bin`, the SD-card gateware/firmware image.
5. Generate the matching ARTIQ `device_db.py` from the same JSON description.

The fallback single command remains controlled by `build.command_template` in the YAML config. This keeps build details explicit while the surrounding tooling stays stable.

## Qt Card Mapping GUI

The Qt GUI is optional because Qt packages are large:

```bash
uv sync --extra gui
uv run madmax gui --config configs/experiments/2in_2out.yaml
# or
./scripts/run_gui.sh configs/experiments/2in_2out.yaml
```

On Ubuntu/Debian X11 systems, Qt may need the native XCB cursor library:

```bash
sudo apt install libxcb-cursor0
```

The GUI lets you choose Kasli-SoC metadata, add ARTIQ cards, assign their EEM ports, edit card-specific JSON options, preview the JSON system description, and write that JSON for the gateware build. It currently includes the cards used by the local `madmax-artiq-zynq` examples and gateware hooks: DIO, Entangler, Urukul, Zotino, Sampler, Mirny, Fastino, Grabber, CoaXPress SFP, Shuttler, and Phaser DRTIO.

If native Qt cannot start on the current system, use the browser fallback:

```bash
uv run madmax web-gui --config configs/experiments/2in_2out.yaml
# or
./scripts/run_web_gui.sh configs/experiments/2in_2out.yaml
```

## Scripts

- `scripts/setup.sh`: create/update the `uv` environment and print workspace status.
- `scripts/init_submodules.sh`: run `git submodule update --init --recursive`.
- `scripts/generate_runtime.sh`: validate and generate settings, `device_db.py`, and a smoke experiment.
- `scripts/build_gateware.sh`: dry-run the gateware build command.
- `scripts/build_from_json.sh`: run the full Kasli-SoC JSON to `boot.bin` flow.
- `scripts/run_gui.sh`: launch the native Python/Qt card mapping GUI.
- `scripts/run_web_gui.sh`: launch the browser card mapping GUI fallback.
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
