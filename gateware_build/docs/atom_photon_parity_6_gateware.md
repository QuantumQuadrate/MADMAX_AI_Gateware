# Atom-Photon Parity 6 Gateware Helper

This document describes the current `atom_photon_parity` custom Entangler logic
as it applies to `atom_photon_parity_6_experiment` in
`repos/qn_artiq_routines/subroutines/experiment_functions.py`.

The purpose of this helper is narrow on purpose: move the short,
timestamp-conditioned part of `atom_photon_parity_6_experiment` into gateware
while leaving slow experiment control in ARTIQ Python.

## Source Files

Gateware and driver files:

- `repos/madmax-entangler-core/entangler/atom_photon_parity_core.py`
- `repos/madmax-entangler-core/entangler/atom_photon_parity_phy.py`
- `repos/madmax-entangler-core/entangler/atom_photon_parity_driver.py`
- `repos/madmax-entangler-core/entangler/atom_photon_parity_registers.py`

Simulation tests:

- `repos/madmax-entangler-core/test/test_atom_photon_parity_core.py`
- `repos/madmax-entangler-core/test/test_atom_photon_parity_phy.py`

Runtime test environment:

- `repos/madmax-artiq-env/atom_photon_parity_6/`

Build configuration:

- `gateware_build/configs/experiments/atom_photon_parity_6.yaml`

## What Parity 6 Does In Python

The timing-critical section of `atom_photon_parity_6_experiment` is:

1. Prepare the atom and optical pumping state.
2. Turn off the FORT around the photon collection window.
3. Pulse excitation light.
4. Gate `SPCM0` and `SPCM1`.
5. Read the first timestamp from each SPCM.
6. If exactly one SPCM clicked, schedule microwave and optional MW+RF pulses at
   offsets from that photon timestamp.
7. Ramp the FORT back up.
8. Run blow-away and atom parity readout.
9. Append datasets for parity readout, SPCM branch, and waveplate angle.

The gateware helper currently targets steps 2 through 6. It does not load atoms,
move waveplates, change DDS frequencies, update Zotino coils, perform blow-away,
run atom readout, or append datasets.

## Hardware Contract

Inputs:

| Input | Meaning |
| --- | --- |
| `input_phys[0]` | `SPCM0` photon edge input |
| `input_phys[1]` | `SPCM1` photon edge input |

Outputs are configurable by index. The recommended parity-6 mapping is:

| Output | Suggested use | Typical idle | Typical active |
| --- | --- | --- | --- |
| 0 | FORT blanking / FORT switch test pulse | high/on | low/off |
| 1 | excitation / GRIN2 switch test pulse | high/off | low/on |
| 2 | microwave switch branch pulse | high/off | low/on |
| 3 | MW+RF switch or debug branch pulse | low/off | high/on |

The core itself does not know those lab meanings. It only drives an output bit
to `active_states[bit]` when the configured attempt or branch window is active;
otherwise it drives `idle_states[bit]`.

## Passthrough Requirement

When `CONFIG.enable = 0`, the PHY drives each owned output pad from the normal
ARTIQ TTL passthrough signal instead of from the parity helper. This is required
for safe debugging: flashing a custom bitstream should not permanently steal the
DIO card from ordinary TTL experiments.

## Real Node 1 Boot Finding

The first parity-6 SD-card image booted on the test Kasli-SoC but did not reach
the network-address stage on the real experiment Node 1. The JTAG UART log
showed SZL loading gateware and runtime, then runtime startup stopped before the
usual I2C, RTIO clocking, network address, and Ethernet-link messages.

The root cause was the generated parity-6 JSON description, not the SD card. It
contained only DIO EEM0 plus the entangler overlay, which matched the test
Kasli-SoC but not the real Node 1 crate. The working real Node 1 description is
`kasli-soc-standalone_node1_with_edgecounters_en.json`: DIO0, DIO1, three
Samplers, Zotino, and three Urukuls on EEM ports 0 through 11. Parity-6 gateware
must preserve that full peripheral list and insert only the atom-photon
entangler overlay on DIO port 0.

The corrected parity-6 description is:

```text
gateware_build/descriptions/atom_photon_parity_6.json
```

It uses variant `SNAQ-Node-1-atom-photon-parity-6`, preserves the working Node 1
peripherals and card hardware revisions, and inserts:

```json
{
  "type": "entangler",
  "uses_reference": false,
  "running_output": false,
  "logic_mode": "atom_photon_parity",
  "ports": [0],
  "overlay": true
}
```

directly after the DIO0 peripheral. The parity runtime device DB targets the
real Node 1 address, `192.168.1.129`.

## DIO/Entangler Overlay Build Contract

The parity-6 system description intentionally lists the same EEM port twice:

```json
{
  "type": "dio",
  "ports": [0],
  "bank_direction_low": "input",
  "bank_direction_high": "output",
  "edge_counter": true
},
{
  "type": "entangler",
  "ports": [0],
  "logic_mode": "atom_photon_parity",
  "overlay": true
}
```

This overlap is not a duplicate-card mistake. The `dio` peripheral is the
physical owner of the EEM port and creates the ordinary ARTIQ TTL PHYs and
`ttlN` device names. The `entangler` peripheral is an overlay on those existing
PHYs. During the gateware build, `repos/madmax-artiq-zynq/src/gateware/entangler_integration.py`
records each DIO PHY as it is created, then the entangler overlay reuses those
recorded input and output PHYs instead of requesting the FPGA pads a second
time.

For parity-6, `hardware.edge_counter: true` in the YAML must be preserved. This
keeps the DIO input counters in the bitstream and places the entangler control
device after those counters. If the JSON is regenerated with edge counters off,
the bitstream puts the entangler at channel `0x000008`, while the parity runtime
`device_db.py` expects it at `0x00000c`.

Output ownership is selected in hardware by the normal ARTIQ output override
signals:

- `CONFIG.enable = 0`: the regular `ttl4` through `ttl7` RTIO outputs drive the
  DIO output pads.
- `CONFIG.enable = 1`: the atom-photon parity core overrides those output PHYs
  and drives the DIO output pads from the gateware branch logic.

The DDB generator follows the same rule. For an overlay entangler, it does not
emit a second synthetic set of TTL devices. It lets the DIO peripheral emit
`ttl0` through `ttl7`, then emits only the entangler control device on the next
RTIO channel. This keeps the software names stable no matter which entangler
logic mode is selected, as long as the selected mode fits the declared DIO
input/output split.

For parity-6 on EEM0, the intended channel order is:

| Device | RTIO channel | Source |
| --- | --- | --- |
| `ttl0`-`ttl3` | `0x000000`-`0x000003` | normal DIO input-side TTLs |
| `ttl4`-`ttl7` | `0x000004`-`0x000007` | normal DIO output-side TTLs |
| `ttl0_counter`-`ttl3_counter` | `0x000008`-`0x00000b` | DIO input edge counters, when enabled |
| `entangler0` / `entangler` | `0x00000c` | overlay control RTIO device |

The JSON order matters: the DIO peripheral for an overlaid EEM port must appear
before the entangler overlay. If `"overlay": true` is set but no matching DIO
has been created first, the gateware build fails instead of silently reverting
to the old standalone-entangler mapping.

The parity helper must still export a complete normal DIO card surface in
`device_db.py`: `ttl0`, `ttl1`, `ttl2`, and `ttl3` are input-side TTLs, and
`ttl4`, `ttl5`, `ttl6`, and `ttl7` are output-side TTLs. The helper consumes
only `ttl0`/`ttl1` as SPCM timestamp inputs; `ttl2`/`ttl3` are generic input
PHYs kept for ordinary ARTIQ use and monitoring. This is why
`gateware_build/configs/experiments/atom_photon_parity_6.yaml` must keep:

```yaml
entangler:
  num_inputs: 2
  num_outputs: 4
  num_generic_inputs: 2
```

If `num_generic_inputs` is accidentally set to `0`, the gateware and generated
`device_db.py` will omit `ttl2` and `ttl3`. That is a build error for parity-6,
not an acceptable runtime mapping.

After changing these counts, regenerate `entangler_settings.toml`, rebuild and
flash the gateware, and regenerate/copy the matching `device_db.py`. The helper
RTIO channel moves when the number of exported TTL/counter channels changes, so
an old bitstream and a new `device_db.py` must not be mixed.

## Core State Machine

The current core has three states:

| State | Behavior |
| --- | --- |
| `IDLE` | Wait for `CONTROL.start`, clear run-local capture state. |
| `ATTEMPT` | Play attempt windows, gate SPCM timestamps, classify after the gate closes. |
| `BRANCH` | Play branch windows relative to the selected photon timestamp. |

The run finishes when:

- exactly one SPCM clicked and the branch window delay has elapsed,
- all attempts were used without an exactly-one-click result,
- the coarse run timeout is reached,
- or the configuration is invalid at start.

## Timing Model

All external ARTIQ driver methods accept machine units. The driver shifts
coarse fields by 3 bits before writing them when the core stores the value in
coarse RTIO cycles.

Important timing values:

| Field | Stored as | Meaning |
| --- | --- | --- |
| `run_length` | coarse cycles | Maximum total run duration. |
| `num_attempts` | integer | Maximum excitation attempts. |
| `attempt_period` | coarse cycles | Spacing between attempt starts. |
| `gate_start`, `gate_stop` | full machine units | SPCM photon gate inside each attempt. |
| `attempt_starts/stops[i]` | coarse cycles | Output `i` window during each attempt. |
| `branch0_starts/stops[i]` | coarse cycles | Output `i` after an `SPCM0_ONLY` click. |
| `branch1_starts/stops[i]` | coarse cycles | Output `i` after an `SPCM1_ONLY` click. |
| `branch_done_delay` | coarse cycles | Time after the click before the run reports done. |

SPCM timestamps are full machine-unit timestamps built from the current coarse
counter and the PHY fine timestamp.

## Photon Classification

During `ATTEMPT`, each SPCM latches the first timestamp whose edge lands inside:

```text
attempt_start + gate_start <= timestamp <= attempt_start + gate_stop
```

After the gate closes, the captured bits are classified:

| Captured bits | Outcome | Result |
| --- | --- | --- |
| `01` | `SPCM0_ONLY` | success, enter `BRANCH` |
| `10` | `SPCM1_ONLY` | success, enter `BRANCH` |
| `00` | `NONE` | retry if attempts remain, otherwise timeout |
| `11` | `BOTH` | retry if attempts remain, otherwise timeout |

The current implementation retries `NONE` and `BOTH` implicitly until
`num_attempts` is exhausted. There are not yet separate retry/stop policies for
`NONE` and `BOTH`.

## Branch Timing

On an exclusive SPCM click, the core records:

- `outcome = SPCM0_ONLY` or `SPCM1_ONLY`,
- `click_ts = captured timestamp`,
- `attempt_index = zero-based attempt number`.

In `BRANCH`, each output bit can have a different window. The branch elapsed
time is:

```text
branch_elapsed = coarse_counter - click_ts_coarse
```

For each output:

```text
active = branch_start <= branch_elapsed < branch_stop
```

The selected branch table comes from `branch0_*` for an `SPCM0_ONLY` click and
from `branch1_*` for an `SPCM1_ONLY` click.

## Register Interface

Write addresses:

| Address | Register | Meaning |
| --- | --- | --- |
| `0x00` | `CONFIG` | bit 0 enables gateware ownership of outputs. |
| `0x01` | `CONTROL` | bit 0 starts a run, bit 1 clears state. |
| `0x02` | `RUN_LENGTH` | coarse run timeout. |
| `0x03` | `NUM_ATTEMPTS` | maximum attempts. |
| `0x04` | `ATTEMPT_PERIOD` | coarse attempt period. |
| `0x05` | `GATE` | packed `gate_stop << 16 | gate_start`, in machine units. |
| `0x06` | `IDLE_STATES` | output bits outside active windows. |
| `0x07` | `ACTIVE_STATES` | output bits inside active windows. |
| `0x08` | `BRANCH_DONE_DELAY` | coarse post-click completion delay. |
| `0x10 + i` | attempt window `i` | packed coarse `stop << 16 | start`. |
| `0x20 + i` | branch-0 window `i` | packed coarse `stop << 16 | start`. |
| `0x30 + i` | branch-1 window `i` | packed coarse `stop << 16 | start`. |

Read addresses:

| Address | Register | Meaning |
| --- | --- | --- |
| `0x80` | `STATUS` | ready/running/success/timeout/invalid/captured/outcome bits. |
| `0x81` | `OUTCOME` | final photon outcome. |
| `0x82` | `CLICK_TS` | selected SPCM timestamp. |
| `0x83` | `SPCM0_TS` | first captured SPCM0 timestamp. |
| `0x84` | `SPCM1_TS` | first captured SPCM1 timestamp. |
| `0x85` | `ATTEMPT_INDEX` | zero-based terminal attempt index. |
| `0x86` | `OUTPUTS` | current output vector readback. |

`STATUS` bits:

| Bit or field | Meaning |
| --- | --- |
| bit 0 | ready |
| bit 1 | running |
| bit 2 | success |
| bit 3 | timeout |
| bit 4 | invalid configuration |
| bits 8-9 | captured SPCM bits |
| bits 16-17 | outcome |

## Configuration Validity

The core rejects a start request as invalid when any of these are true:

- `num_attempts == 0`
- `attempt_period == 0`
- `run_length == 0`
- `gate_start >= gate_stop`
- `gate_stop_coarse >= attempt_period`

An invalid start produces a done event with `timeout = 1` and
`invalid_config = 1`.

## Test Plan

Run the software simulation tests first:

```bash
pytest repos/madmax-entangler-core/test/test_atom_photon_parity_core.py
pytest repos/madmax-entangler-core/test/test_atom_photon_parity_phy.py
```

Then generate and validate the integration config:

```bash
uv run madmax validate --config gateware_build/configs/experiments/atom_photon_parity_6.yaml
uv run madmax generate-settings --config gateware_build/configs/experiments/atom_photon_parity_6.yaml
uv run madmax generate-device-db --config gateware_build/configs/experiments/atom_photon_parity_6.yaml
uv run madmax generate-experiment --config gateware_build/configs/experiments/atom_photon_parity_6.yaml
uv run madmax build-gateware --config gateware_build/configs/experiments/atom_photon_parity_6.yaml --dry-run
```

After flashing matching gateware, use the ARTIQ experiments in:

```text
repos/madmax-artiq-env/atom_photon_parity_6/repository/
```

Recommended hardware order:

1. `atom_photon_parity_6_smoke.py`
2. `atom_photon_parity_6_no_click.py`
3. `atom_photon_parity_6_spcm0_loopback.py`
4. `atom_photon_parity_6_spcm1_loopback.py`
5. `atom_photon_parity_6_timing_scan.py`
6. `atom_photon_parity_6_stress.py`
7. `atom_photon_parity_6_benchmark.py`

The loopback tests intentionally use output pulses as fake SPCM photons. They
are for validating gateware timing and branch selection before connecting the
real photon detectors.

## Verification Results

Recorded on 2026-05-25 from this workspace:

| Check | Result |
| --- | --- |
| `uv run pytest` | Passed: 26 tests, including `tests/gateware/test_gateware_build_contract.py`. |
| `uv run madmax validate --config gateware_build/configs/experiments/atom_photon_parity_6.yaml` | Passed. |
| `uv run madmax build-gateware --config gateware_build/configs/experiments/atom_photon_parity_6.yaml --dry-run` | Passed and prepared `gateware_build/descriptions/atom_photon_parity_6.json`, `gateware_build/generated/entangler_settings.toml`, and artifact `gateware_build/artifacts/atom_photon_parity_6-20260525-153834-266209`. |
| `pytest repos/madmax-entangler-core/test/test_atom_photon_parity_core.py repos/madmax-entangler-core/test/test_atom_photon_parity_phy.py` | Blocked outside the gateware Python environment because `migen` is not installed in the top-level `uv` environment. |
| `nix develop --command pytest ...` in `repos/madmax-entangler-core` | Blocked because the dev shell provides `migen`/ARTIQ but not `pytest`. |

The validated integration result is the DIO overlay contract: the generated
parity-6 description keeps DIO EEM0 as normal `ttl0` through `ttl7`, keeps input
edge counters enabled, and places the atom-photon parity control device at RTIO
channel `0x00000c` for the matching bitstream/runtime pair.
