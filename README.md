# MADMAX AI Gateware

`MADMAX-AI-Gateware` is the integration and automation layer for MADMAX Kasli-SoC gateware work. It does not copy gateware code from the underlying projects. Instead, it references them as Git submodules and provides deterministic tooling around a high-level experiment YAML file.

The core design rule is simple: an AI assistant should change the experiment config first, then Python tooling validates the request and generates the matching runtime files. Generated files are build artifacts, not the source of truth.

## Repositories

This workspace orchestrates:

- `repos/madmax-artiq-env`: Python/ARTIQ environment reference.
- `repos/madmax-artiq-zynq`: Kasli-SoC and ARTIQ Zynq gateware build flow.
- `repos/madmax-entangler-core`: custom Migen/Entangler logic.

## Documentation

- [Entangler logic across branches](docs/entangler_logic_branches.md): compares
  the original `madmax-entangler-core` logic with the atom-photon parity mode
  branch.
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

## Custom Entangler Logic Workflow

Use this workflow when the experiment needs new gateware behavior, not just a
different YAML configuration. The goal is to let Codex create a new
`madmax-entangler-core` branch, wire `madmax-artiq-zynq` to that branch, create a
matching ARTIQ runtime environment, and write experiments that prove the logic
before any hardware flashing.

Start with a prompt that is explicit about behavior and test expectations:

```text
Create custom entangler logic named <logic_name>.
Base it on <master/artiq-integration/atom-photon branch>.

Required behavior:
- ...
- Passthrough is required: when the custom logic is disabled, every DIO channel
  owned by the custom gateware must either behave like its normal ARTIQ TTL
  device or be explicitly documented as unavailable.

Inputs:
- ...

Outputs:
- ...

Success/failure rules:
- ...

Test experiment behavior:
- ...
```

### 1. Create The Entangler-Core Branch

Codex should create a feature branch inside the entangler core submodule:

```bash
cd repos/madmax-entangler-core
git checkout -b feature/<logic-name>
```

For experimental logic, prefer a separate implementation path instead of
mutating the legacy `core.py` directly:

```text
entangler/<logic_name>_core.py
entangler/<logic_name>_phy.py
entangler/<logic_name>_driver.py
entangler/<logic_name>_registers.py
test/test_<logic_name>_core.py
test/test_<logic_name>_phy.py
```

Only move behavior into shared files such as `entangler/core.py` after it is
clearly reusable.

### Required Passthrough Behavior

Every custom gateware design must include a disabled or bypass mode. This is a
hard requirement, not an optional convenience. The intended contract is:

- `enable = 0`: custom logic is ignored and the DIO channels pass through to
  normal ARTIQ TTL behavior wherever physically possible.
- `enable = 1`: custom logic owns only the channels it needs.
- Any channel that cannot be passed through must be called out in the design
  notes, JSON/card options, runtime driver, and tests.

This keeps a custom Entangler build from permanently stealing a DIO card during
debugging or mixed experiments. Tests for a new logic mode should prove both the
custom path and the disabled passthrough path.

### 2. Point ARTIQ-Zynq At The New Logic

During local development, use a path input in
`repos/madmax-artiq-zynq/flake.nix`. This lets Nix build the local working tree
without requiring every small change to be pushed first:

```nix
inputs.entangler-core = {
  url = "path:../madmax-entangler-core";
  inputs.artiqpkgs.follows = "artiq";
  inputs.nixpkgs.follows = "artiq/nixpkgs";
};
```

Then update the lock file from `repos/madmax-artiq-zynq`:

```bash
nix flake lock --update-input entangler-core
```

After the custom logic is tested and pushed, switch the same input to the remote
feature branch for reproducibility:

```nix
inputs.entangler-core = {
  url = "git+https://github.com/QuantumQuadrate/madmax-entangler-core.git?ref=feature/<logic-name>";
  inputs.artiqpkgs.follows = "artiq";
  inputs.nixpkgs.follows = "artiq/nixpkgs";
};
```

Update the lock file again so the build records the exact entangler-core commit.

### 3. Create A Matching ARTIQ Environment

Create a dedicated runtime environment under `repos/madmax-artiq-env/`, usually
by copying the existing `entangler` environment:

```text
repos/madmax-artiq-env/<logic_name>/
  pyproject.toml
  settings.toml
  device_db.py
  repository/<logic_name>_smoke.py
  repository/<logic_name>_loopback.py
  repository/<logic_name>_timing_scan.py
  repository/<logic_name>_stress_test.py
  README.md
  run_artiq.sh
```

The environment should pin the same entangler-core branch or revision that the
gateware build uses. Runtime settings in `settings.toml` must match the compiled
bitstream settings.

### 4. Write Experiments In Layers

The test experiments should become progressively more serious:

| Experiment | Purpose |
| --- | --- |
| smoke | initialize the driver, configure the core, run once, print status |
| loopback | prove physical input/output mapping with TTL loopbacks |
| timing scan | sweep gate windows, output windows, or branch timings |
| stress test | run many repetitions and count successes, timeouts, and failure reasons |
| benchmark | compare CPU-side branching against gateware-side branching when relevant |

Keep dataset appends, plots, and analysis in host Python. Keep timing-critical
branching and reaction logic in gateware.

### 5. Verification Ladder

Run the checks in this order:

```bash
pytest repos/madmax-entangler-core/test/test_<logic_name>*.py
cd repos/madmax-artiq-zynq
nix flake check
cd ../../
uv run madmax validate --config configs/experiments/<logic_name>.yaml
uv run madmax generate-settings --config configs/experiments/<logic_name>.yaml
uv run madmax generate-device-db --config configs/experiments/<logic_name>.yaml
uv run madmax generate-experiment --config configs/experiments/<logic_name>.yaml
uv run madmax build-gateware --config configs/experiments/<logic_name>.yaml --dry-run
```

Only after the logic tests, generated runtime files, and dry-run build plan look
right should a real gateware build or hardware flashing be considered.

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

The browser GUI also includes a **Custom Logic** tab for the Codex-driven
workflow described above.

## Custom-Logic GUI

Start the browser GUI from the repository root:

```bash
uv run madmax web-gui --config configs/experiments/2in_2out.yaml
```

Or use the script wrapper:

```bash
./scripts/run_web_gui.sh configs/experiments/2in_2out.yaml
```

By default it serves:

```text
http://127.0.0.1:8765
```

Open that URL and choose **Custom Logic** in the top bar. To keep the browser
from opening automatically, or to use a different port:

```bash
uv run madmax web-gui --config configs/experiments/2in_2out.yaml --no-open --port 8766
```

Stop the GUI with `Ctrl+C` in the terminal that started it.

The custom-logic GUI does not try to design gateware visually from scratch.
Codex is better at turning a written specification into code. The GUI guides the
workflow, records the prompt/specification, and makes the state of the three
repositories obvious.

It can:

- **Logic request**: logic name, base branch, input/output counts, mode
  description, success/failure rules, and test expectations.
- **Branch and dependency wiring**: create the entangler-core branch, choose
  local path mode or remote branch mode, and update the `madmax-artiq-zynq`
  flake input.
- **ARTIQ environment scaffold**: create the matching
  `repos/madmax-artiq-env/<logic_name>/` environment and select smoke,
  loopback, timing-scan, stress, or benchmark experiment templates.
- **Codex execution**: write the structured request to `ai/requests/` and, when
  the local Codex CLI is available, run `codex exec` against the workspace.
- **Verification dashboard**: run tests, validation, generation, Nix flake
  checks, and dry-run builds with visible logs and pass/fail status.
- **Handoff summary**: show changed files, active branches, exact flake input,
  generated runtime paths, and the next safe command.

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
