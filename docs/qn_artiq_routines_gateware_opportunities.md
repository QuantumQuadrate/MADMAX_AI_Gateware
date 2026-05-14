# qn_artiq_routines Organization And Gateware Opportunities

This note maps the newly added `repos/qn_artiq_routines` submodule into the
MADMAX gateware workflow. The goal is not to port every ARTIQ experiment into
gateware. The goal is to identify where custom Entangler logic would remove
RTIO timing pressure, make branch decisions faster, or make repeated
photon/atom-response loops more deterministic.

Submodule snapshot inspected:

- Path: `repos/qn_artiq_routines`
- Remote: `git@github.com:QuantumQuadrate/qn_artiq_routines.git`
- Branch: `main`
- Commit: `0876311`

## Repository Organization

`qn_artiq_routines` is an ARTIQ experiment repository for the Saffman-group
quantum network experiment. It has 200+ Python files plus analysis notebooks and
instrument helpers. The important directories are:

| Path | Role |
| --- | --- |
| `*.py` at repo root | Main dashboard-facing experiments and experiment managers. |
| `subroutines/` | Shared kernel subroutines used by the root experiments. The central file is `subroutines/experiment_functions.py`. |
| `utilities/` | Common experiment infrastructure: `BaseExperiment`, device aliases, conversions, HDF5 writing, node-specific JSON config. |
| `device_db/` | Several ARTIQ device database variants for nodes and clocking/card setups. |
| `MOT_experiments/` | MOT-specific scan, monitor, and tuning experiments. |
| `tests/` | Hardware tests, timing probes, diagnostics, and one-off development experiments. |
| `applets/` | Dashboard applets for live plotting experiment datasets. |
| `Analysis/` | Analysis notebooks and generated plots for atom, photon, microwave, tomography, and PostgreSQL data. |
| `fitting/` | Reusable fitting models for analysis and scan optimization. |
| `ndsp/`, `third_party/` | Device-server and vendor/instrument integration code. |
| `examples/` | Standalone or historical example experiments. |

## Runtime Architecture

Most major experiments use `utilities/BaseExperiment.py`. `BaseExperiment`
imports datasets from `ExperimentVariables.py`, loads device aliases from
`utilities/config/<node>/device_aliases.json`, attaches ARTIQ devices, and
provides common initialization and dataset-saving behavior.

The node-specific TTL names matter for gateware planning. On `alice`,
`BaseExperiment` maps:

- `ttl_SPCM0` / `ttl_SPCM0_counter` to `ttl0` / `ttl0_counter`
- `ttl_SPCM1` / `ttl_SPCM1_counter` to `ttl1` / `ttl1_counter`
- `ttl_microwave_switch` to `ttl4`
- `ttl_repump_switch` to `ttl5`
- `ttl_exc0_switch` to `ttl6`
- `ttl_pumping_repump_switch` to `ttl7`
- `ttl_SPCM0_logic` to `ttl12`
- `ttl_GRIN2_switch` to `ttl13`
- `ttl_GRIN1_switch` to `ttl14`
- `ttl_SPCM1_logic` to `ttl15`

That is a natural DIO/Entangler mapping: SPCM inputs on one bank, experiment
action outputs on another bank, and optional logic/debug TTLs.

## Required Passthrough Rule

Every custom logic mode proposed in this document must include disabled-mode
passthrough. This is a required acceptance criterion for any design that owns a
DIO card or DIO bank.

- `enable = 0`: the custom logic is disabled or ignored, and the DIO channels
  behave like normal ARTIQ TTL inputs/outputs wherever physically possible.
- `enable = 1`: the custom logic owns only the channels needed for that
  experiment mode.
- Any channel that cannot be passed through must be explicitly documented in the
  gateware design, JSON/card options, runtime driver, and tests.

This requirement matters for `qn_artiq_routines` because many experiments share
the same physical TTL channels. A custom photon or parity mode must not prevent
ordinary ARTIQ use of the DIO card when the custom mode is disabled.

## Main Experiment Families

### Setup And Infrastructure

- `ExperimentVariables.py`: dashboard experiment for shared datasets such as
  timings, powers, microwave frequencies, photon collection windows, thresholds,
  and booleans.
- `AOMsCoils.py`: manual control panel for MOT/FORT/cooling/pumping/excitation
  AOMs, coils, microwaves, waveplates, and optional laser feedback.
- `ExperimentCycler.py`: runs a selected function from
  `subroutines/experiment_functions.py` repeatedly.
- `GeneralVariableScan.py`: scans one or more `ExperimentVariables` while
  running a selected experiment function.
- `GeneralVariableOptimizer.py`: M-LOOP based optimizer for selected variables
  and cost functions.

These are orchestration tools. They should stay mostly runtime-side, but they
can become clients of gateware modes.

### Atom Loading And Readout

- `SimpleAtomTrappingNoChopping.py`: loads MOT/FORT and performs simple SPCM
  readout without chopped readout.
- `AtomLoadingOptimizer.py` and `AtomLoadingOptimizer_load_until_atom.py`:
  optimize loading behavior using repeated SPCM checks and feedback.
- `SingleAtomTrapLifetime.py`: two-shot trap lifetime experiment with variable
  delay between SPCM readouts.
- `SingleAtomTemperature.py`: release/recapture style temperature measurement.

Shared subroutines include:

- `load_MOT_and_FORT`
- `load_MOT_and_FORT_until_atom`
- `load_MOT_and_FORT_until_atom_recycle`
- `load_until_atom_smooth_FORT_recycle`
- `first_shot`, `second_shot`, `atom_parity_shot`
- `chopped_RO`, `record_chopped_RO`

Gateware opportunity: medium. The millisecond loading/feedback pieces are not a
good gateware fit, but repeated readout windows and SPCM threshold decisions
could become small gateware-assisted primitives.

### Microwave And Atom-State Scans

- `Microwaves_scans.py`: chooses microwave Rabi/Ramsey/map experiments and
  updates relevant datasets after fitting.
- `MicrowaveScanOptimizer.py`: optimizer wrapper around microwave scan logic.

Shared experiment functions include many variants:

- `microwave_Rabi_experiment`
- `microwave_Rabi_2_experiment`
- `microwave_Ramsey_00_experiment`
- `microwave_Ramsey_11_experiment`
- `microwave_map01_map11_experiment`
- `microwave_map00_map0m1_experiment`
- `microwave_map01_MWRFm11_experiment`
- `atom_state_mapping`, `atom_rotation_x`, `atom_rotation_y`

Gateware opportunity: low to medium. DDS frequency/phase changes and scan
orchestration belong in ARTIQ, but fixed TTL microwave-switch pulse patterns
relative to a photon timestamp are a strong fit when embedded inside the
atom-photon branch logic.

### Single Photon And Atom-Photon Experiments

The strongest gateware candidates live in `subroutines/experiment_functions.py`:

- `single_photon_experiment`
- `single_photon_experiment_atom_loading_advance`
- `single_photon_experiment_2_atom_loading_advance`
- `single_photon_experiment_3_atom_loading_advance`
- `single_photon_experiment_3_atom_loading_advance_node2`
- `atom_photon_parity_1_experiment` through `atom_photon_parity_6_experiment`
- `atom_photon_tomography_experiment`

These routines perform sequences like:

1. Load/recycle an atom.
2. Do optical pumping.
3. Turn FORT off briefly around an excitation attempt.
4. Pulse excitation TTLs.
5. Open SPCM0/SPCM1 gates for a short photon collection window.
6. Read first photon timestamps.
7. Branch on exactly-one-click outcomes.
8. Schedule microwave and optional MW+RF pulses at offsets from the photon
   timestamp.
9. Do blowaway/parity/readout and log outcome datasets.

Gateware opportunity: high. Steps 3-8 are exactly the timing-critical path where
the CPU-side kernel code is doing custom logic. This should become one or more
custom Entangler logic modes.

### MOT Experiments

`MOT_experiments/` contains:

- `CoilScanFindMOT.py`
- `CoilScanSPCMCount.py`
- `CoilScanSPCMCount1D.py`
- `Coils-SPCMCounts.py`
- `MOTDetuningAndGradBScan.py`
- `MOTLoadDelay.py`
- `MOTMonitorEverything.py`
- `MOT_Temperature.py`
- `MonitorMOTandExternalBeamPositions.py`
- `SamplerMOTCoilAndBeamBalanceTune.py`

Gateware opportunity: low. These are mostly slow scans, monitoring, coil/DDS
tuning, and sampler/camera workflows. The reusable part is SPCM counting in
fixed gates, which standard edge counters or the legacy Entangler can already
support.

### Tests And Diagnostics

The `tests/` directory contains useful hardware probes:

- SPCM/gate timing: `A1-SPCMCount.py`, `A2-SPCMGateTimeVsCounts.py`,
  `A2-SPCMGateRiseTimeTest.py`, `A2-ExcitationSPCMGateStartTime.py`
- TTL logic/readout tests: `A11-Testing_TTL_logic_gates.py`,
  `A12-Testing_chopped_RO_with_sensitivity.py`,
  `A13-Testing_chopped_RO_with_Logic.py`
- DDS/microwave tests: `A7-DDS_RAM_FORT_test.py`,
  `A8-Urukul-Sync-Calibrate.py`, `A9-SPCM_microwave_delay_test.py`,
  `A10-Simulate_MW_RF_rotation.py`, `MicrowaveTest.py`
- Feedback and monitor tests: `AOMFeedbackTest.py`,
  `AOMFeedbackMutlipleSetpointsTest.py`, `A14-Test_feedback_on_MOT5.py`,
  `A15-Testing_AOM_Stabilizer_2026.py`

Gateware opportunity: useful as verification harnesses. The TTL/SPCM tests can
be adapted into loopback and timing-scan tests for custom Entangler modes.

## Proposed Custom Entangler Logic Modes

### 1. `photon_collection`

Purpose: encapsulate one excitation attempt.

Inputs:

- `SPCM0`
- `SPCM1`
- optional external start/reference trigger

Outputs:

- FORT blanking/on signal
- excitation AOM switch
- optional debug/running outputs

Behavior:

- Provide `enable = 0` passthrough for all owned DIO channels.
- On start, schedule FORT off/on around the photon collection window.
- Pulse excitation at configured offset and width.
- Open SPCM0/SPCM1 gates at `gate_start_offset_mu`.
- Capture first timestamp from each detector.
- Return status bits: no click, SPCM0 only, SPCM1 only, both, invalid/timeout.

Used by:

- `single_photon_experiment*`
- `atom_photon_tomography_experiment`
- early verification of photon collection without microwave branch actions

Why it helps:

- Removes repeated `gate_rising`/`timestamp_mu` bookkeeping from Python.
- Creates a stable hardware contract for short photon windows.
- Gives a clean place to test detector timing against excitation timing.

### 2. `atom_photon_parity`

Purpose: implement the detection-conditioned branch logic currently written in
the atom-photon parity routines.

Inputs:

- `SPCM0`
- `SPCM1`
- start/run control from ARTIQ

Outputs:

- FORT control
- excitation switch
- microwave switch
- optional MW/RF gate TTL
- optional blowaway/readout trigger/debug TTLs

Behavior:

- Provide `enable = 0` passthrough for all owned DIO channels.
- Run repeated excitation attempts up to `n_excitation_attempts`.
- Classify photon outcome.
- If SPCM0-only or SPCM1-only, schedule branch action table relative to that
  detector timestamp.
- Support two branch tables, because the current routines use mirrored logic for
  SPCM0 and SPCM1 clicks.
- Return compact results: branch id, click timestamp, attempt index, terminal
  reason, and status flags.

Used by:

- `atom_photon_parity_1_experiment` through `atom_photon_parity_6_experiment`

Why it helps:

- The current code branches in Python after a timestamp read and then schedules
  `at_mu(click_time + offset)` microwave/MW+RF actions. Moving that to gateware
  cuts host latency and makes the click-to-action path deterministic.

### 3. `chopped_readout`

Purpose: make repeated chopped readout/optical pumping/blowaway pulse trains a
small hardware sequencer.

Inputs:

- one or two SPCM inputs
- start/run control

Outputs:

- cooling/readout TTLs
- repump/pumping TTLs
- FORT blanking or mode TTL
- optional AOM switch TTLs

Behavior:

- Provide `enable = 0` passthrough for all owned DIO channels.
- Play configured chop tables with windowed SPCM counting.
- Accumulate counts for first shot, second shot, or parity shot.
- Return counts and status.

Used by:

- `record_chopped_RO`, `chopped_RO`
- `first_shot`, `second_shot`, `atom_parity_shot`
- `record_chopped_optical_pumping`, `chopped_optical_pumping`
- `record_chopped_blow_away`, `chopped_blow_away`

Why it helps:

- Standardizes a repeated timing pattern.
- Frees Python from dense TTL pulse sequencing.
- Gives better reproducibility when readout sensitivity depends on sub-us pulse
  alignment.

### 4. `atom_loaded_discriminator`

Purpose: gate two SPCM counters and make a threshold decision in hardware.

Inputs:

- `SPCM0`
- `SPCM1`

Outputs:

- loaded/not-loaded status
- optional "loaded" debug TTL

Behavior:

- Provide `enable = 0` passthrough for all owned DIO channels.
- Count SPCM events in a configurable atom-check window.
- Average or combine SPCM counts.
- Compare against `single_atom_threshold_for_loading`.
- Return loaded/not-loaded and raw counts.

Used by:

- `load_MOT_and_FORT_until_atom`
- `load_MOT_and_FORT_until_atom_recycle`
- `load_until_atom_smooth_FORT_recycle`
- `AtomLoadingOptimizer*`

Why it helps:

- This can reduce kernel overhead in repeated load checks, but it does not need
  a fully custom core unless CPU-side checks become a bottleneck.

### 5. `ttl_logic_test`

Purpose: formalize the existing TTL logic-gate tests into a build-time
verification core.

Inputs:

- two or more TTL inputs

Outputs:

- combinational or registered logic results
- loopback/timer outputs

Behavior:

- Provide `enable = 0` passthrough for all owned DIO channels.
- AND/NAND/XOR/parity outputs.
- Timestamp selected loopback edges.
- Report measured delay/span.

Used by:

- `tests/A11-Testing_TTL_logic_gates.py`
- existing `and_nand_test` gateware work

Why it helps:

- Good smoke test for the custom-logic plumbing.
- Less important scientifically than the photon/parity modes, but excellent for
  validating DIO mapping and branch defaults.

## Opportunity Ranking

| Rank | Target | Gateware value | Notes |
| --- | --- | --- | --- |
| 1 | `atom_photon_parity` | Very high | Directly replaces timestamp-conditioned branch code. |
| 2 | `photon_collection` | High | Smaller first milestone; useful across photon and tomography experiments. |
| 3 | `chopped_readout` | Medium-high | Reusable, deterministic pulse/count engine. |
| 4 | `ttl_logic_test` | Medium | Strong verification target and already aligned with `and_nand_test`. |
| 5 | `atom_loaded_discriminator` | Medium | Helpful if load checks dominate or need faster reaction. |
| 6 | MOT scans / coil scans / feedback | Low | Mostly slow control, optimization, and monitoring. Keep in ARTIQ. |

## Suggested Implementation Path

1. Start with `photon_collection`.
   - Build the smallest core that can pulse excitation, gate SPCM0/SPCM1, and
     return first-click classification.
   - Prove disabled-mode passthrough before validating the custom photon path.
   - Use tests inspired by `TimeTagging.py`, `A2-SPCMGateTimeVsCounts.py`, and
     `A2-ExcitationSPCMGateStartTime.py`.

2. Extend to `atom_photon_parity`.
   - Add two configurable branch action tables.
   - Keep DDS frequency/phase setup in ARTIQ.
   - Gateware should drive TTL switches at timestamp-relative offsets.

3. Add a runtime bridge in `qn_artiq_routines`.
   - The ARTIQ experiment should configure the custom Entangler device, run it,
     and receive compact result words.
   - Existing dataset names can remain stable by translating result words back
     into `SPCM0_SinglePhoton`, `SPCM1_SinglePhoton`, `BothSPCMs_parity_RO`,
     `n_excitation_cycles`, and timestamp datasets.

4. Add a MADMAX experiment YAML per logic mode.
   - Example branches:
     - `feature/photon-collection`
     - `feature/atom-photon-parity`
     - `feature/chopped-readout`
   - The card mapper already turns `feature/atom-photon-parity` into
     `"logic_mode": "atom_photon_parity"` for Entangler card defaults.

5. Keep slow-control code out of gateware.
   - Laser feedback, camera work, waveplate motion, M-LOOP, PostgreSQL/logging,
     fitting, and scan selection should stay in Python.

## Open Questions Before Writing A Core

- Which DIO EEM ports will the custom Entangler own on Alice and Bob?
- Should SPCM inputs use TTL SERDES, edge counters, or the existing Entangler
  input PHY path?
- Which TTL outputs must be driven by gateware in parity mode, and which can
  remain ordinary ARTIQ TTLs?
- For every owned channel, what is the exact `enable = 0` passthrough behavior?
- Are branch action timings fixed enough for a small action table, or do they
  need arbitrary runtime upload?
- Does the first production target need only SPCM0/SPCM1 classification, or the
  full microwave/MW+RF branch sequence?
- Should result words prioritize raw timestamps, compact status, or compatibility
  with current datasets?

## Bottom Line

The best first opportunity is not "one entangler core for every experiment."
It is a small family of reusable custom modes:

- `photon_collection` for detector gate/timestamp/classification
- `atom_photon_parity` for click-conditioned branch actions
- `chopped_readout` for repeated pulse/count windows

Those modes cover the experiments where custom gateware has a real payoff. The
rest of `qn_artiq_routines` should use those modes as accelerators while keeping
its scan, optimization, feedback, and analysis logic in ARTIQ/Python.
