# Kasli-SoC Populated-Carrier Boot Diagnostic Notes

Date: 2026-05-27

Related focused finding:
`ai/build_provenance_findings_2026-05-27.md` documents why the populated-system
failure is now being treated first as a generated-image provenance problem.

## Current Summary

Update after comparison with a known-good populated-system `boot.bin`: the
populated hardware itself is not the root problem. A separate image boots the
same populated crate correctly, so the main suspect is now the generated build
output: gateware/firmware pairing, CSR metadata freshness, JSON target options,
or the boot packaging flow.

The strongest concrete build-flow issue found so far is stale CSR provenance.
In this workspace, `repos/madmax-artiq-zynq/build/pl.rs`,
`repos/madmax-artiq-zynq/build/rustc-cfg`, and
`repos/madmax-artiq-zynq/build/mem.rs` were timestamped `2026-05-27 08:12`,
while `repos/madmax-artiq-zynq/build/gateware/top.bit` was timestamped
`2026-05-27 11:22` and `repos/madmax-artiq-zynq/build/runtime.bin` was
timestamped `2026-05-27 12:51`. That allows firmware to be built against a CSR
map that may not describe the bitstream packaged into `boot.bin`.

Mitigation added in this workspace:

- `repos/madmax-artiq-zynq/src/Makefile` now forces regeneration of `pl.rs`,
  `rustc-cfg`, and `mem.rs` before firmware builds.
- `scripts/build_from_json.sh` now provides a single JSON-to-`boot.bin` path
  that builds `top.bit`, deletes stale CSR metadata, builds matching firmware,
  packages `boot.bin`, and writes a hash manifest.
- The example `build.command_template` values now call that script instead of
  stopping after raw bitstream generation.

The populated Kasli-SoC carrier failure is therefore being rerouted as a build
provenance problem first, not as evidence that the populated crate is bad.

The populated Kasli-SoC carrier failure is not caused by the ARTIQ description
including EEM peripherals. The same no-EEM gateware image boots on an unpopulated
carrier but fails on the populated carrier. The no-EEM JSON has:

```json
"peripherals": []
```

The diagnostic sequence has shown that the populated carrier can:

- load SZL
- mount the SD card
- load the FPGA bitstream
- load and enter the runtime
- initialize runtime RAM
- enable GIC interrupts
- initialize I2C
- detect the PCA9548 I2C switch
- initialize both Kasli I/O expanders
- configure and lock the Si5324
- initialize Ethernet far enough to print `network addresses`
- pass RTIO management startup when the known RTIO-core CSR writes are skipped
- start analyzer, moninj, and kernel control
- keep the TCP control accept task and network event loop alive when the early
  RTIO-facing background services are skipped
- complete `identifier_read()` when the diagnostic PL `sys` fabric is clocked
  directly from Zynq PS FCLK and the standalone `sys_crg` block is absent
- complete a dummy generated `CSRStorage` write when the active PL `sys` fabric
  is clocked directly from Zynq PS FCLK and the normal AXI2CSR/CSR path is used
- reach network address assignment with standalone SYS_CRG/MMCM-driven `sys`
  restored, but then hang on the same explicit post-network `identifier_read()`

The populated carrier blocks at multiple PL/RTIO CSR accesses in the original
standalone SYS_CRG/MMCM-style fabric unless those accesses are skipped:

- `identifier_read()` hangs at the PL CSR identifier block in the original
  standalone-clock image, but succeeds in test `13` with PS-FCLK-driven `sys`.
- `identifier_read()` also hangs in test `14` after restoring standalone
  SYS_CRG/MMCM-driven `sys`, even though SZL, runtime initialization, Si5324
  lock, and Ethernet address assignment all complete first.
- `identifier_read()` also hangs in test `16` even though the standalone
  SYS_CRG clock-switch CSR default is low and the generated Verilog shows
  `sys_crg_storage_full = 1'd0`; this means the intended SED-spread write in
  test `16` was not reached.
- `csr::rtio_core::sed_spread_enable_write(0)` hangs in test `17` even after
  all `identifier_read()` calls are skipped, standalone SYS_CRG remains present,
  its clock-switch CSR default stays low, and the firmware SYS/RTIO
  clock-switch write remains skipped.
- `csr_bridge_probe::sys_heartbeat_read()` hangs in test `18` before the
  intended timeout-safe SED-spread write is reached. The image used a
  bootstrap-clocked AXI2CSR response path and added a PL-side CSR observer, but
  the firmware still performed ordinary blocking reads of that observer before
  attempting the decisive write. The UART stops immediately after `SED
  spreading disabled by default`, before `diag: experiment 18 bootstrap AXI/CSR
  probe armed ...`.
- `csr::rtio_core::sed_spread_enable_write(0)` also hangs in test `19` when the
  firmware performs no post-network PL CSR reads before the write and the
  AXI2CSR path is clocked from the bootstrap clock. The UART reaches `diag:
  before experiment 19 bootstrap AXI write-only SED spread CSR write value 0
  address=0x80001008` and never prints the after-write marker.
- `csr::bootstrap_write_sink::value_write(0)` hangs in test `20` when the
  first intentional post-network PL CSR transaction is a write to a dummy
  bootstrap-domain `CSRStorage(32)` at `0x80001800`. The UART reaches `diag:
  before experiment 20 bootstrap-local write sink CSR write value 0
  address=0x80001800` and never prints the after-write marker.
- `csr::ps_fclk_write_sink::value_write(0)` completes in test `21` when
  standalone `SYS_CRG` is absent, the active PL `sys` fabric is driven directly
  from Zynq PS FCLK, AXI2CSR is not bootstrap-renamed, and the first intentional
  post-network PL CSR transaction is a write to a dummy `CSRStorage(32)` at
  `0x80001000`. The UART prints both the before-write and after-write markers,
  then continues into the network poll heartbeat loop.
- `csr::standalone_sys_write_sink::value_write(0)` hangs in test `22` when
  standalone `SYS_CRG` is restored, AXI2CSR remains normal, and the first
  intentional post-network PL CSR transaction is the same dummy generated
  `CSRStorage(32)` write at `0x80001800`.
- `csr::standalone_sys_write_sink::value_write(0)` also hangs in test `23` when
  standalone `SYS_CRG` remains present, AXI2CSR remains normal, and the SYS_CRG
  MMCM is forced onto the bootstrap clock input instead of the external/main
  CDR/SI5324-derived input path.
- `pl::csr::sys_crg::clock_switch_write(1)` hangs during SYS/RTIO clock switch.
- `csr::rtio_core::sed_spread_enable_write(0)` is the next confirmed hang after
  Ethernet comes up.
- `pl::csr::sys_crg::current_clock_read()` hangs after Ethernet comes up, even
  though it is a read-only SYS_CRG `CSRStatus` probe.

This makes the current working hypothesis: the populated carrier is not failing
because the JSON enumerates cards, the flake, or the basic BOOT packaging. It is
failing when specific clock/bridge integrations are restored around the
generated PL CSR path. Experiment `20` showed that a bootstrap-domain dummy CSR
write can block in the bootstrap-renamed AXI2CSR diagnostic image, but
experiment `21` proves that a dummy generated CSR write can complete on the
same populated carrier when `sys` is PS-FCLK-driven and AXI2CSR is normal. The
same populated carrier when `sys` is PS-FCLK-driven and AXI2CSR is normal.
Experiment `22` proves that restoring standalone `SYS_CRG` with normal AXI2CSR
is enough to hang a dummy generated CSR write. Experiment `23` proves that this
does not require the external/main CDR/SI5324-derived SYS_CRG input path: the
same dummy write still hangs when the SYS_CRG MMCM is held on the bootstrap
clock input. The strongest remaining suspect is standalone SYS_CRG/MMCM/reset
integration itself, or the PS GP AXI to generated CSR completion path when the
CSR fabric is clocked by standalone SYS_CRG-driven `sys`.

## Artifact And Result Index

| Artifact | Purpose | Populated-carrier result |
| --- | --- | --- |
| `00_empty` | Baseline no-EEM image | Fails on populated carrier, boots on unpopulated carrier. |
| `01_empty_startup_diag` | Add early runtime breadcrumbs | Stops after `diag: before identifier_read`. |
| `02_empty_skip_ident` | Skip only `identifier_read` | Reaches I2C, I/O expanders, Si5324 lock; stops at `Switching SYS clocks...`. |
| `03_empty_skip_ident_skip_rtio_clock_switch` | Skip `identifier_read` and SYS/RTIO clock switch | Reaches `network addresses`; stops after `SED spreading disabled by default`. |
| `04_empty_skip_ident_skip_rtio_csrs` | Skip known failing identifier/SYS/RTIO CSR writes and instrument comms startup | Reaches `after kernel control start`; no later UART output, likely idle in network/control loop. |
| `05_empty_network_loop_heartbeat` | Add markers around management/control task startup and periodic network poll heartbeat | Reaches `entering network poll loop`; no control-task or heartbeat output observed. |
| `06_empty_network_poll_probe` | Add first-iteration markers around timer read, `Sockets::poll()`, Ethernet link check, and first async yield | Reaches `first network loop before yield`; no spawned task runs afterward. |
| `07_empty_control_loop_reachability` | Skip early RTIO-facing spawned tasks and check whether control/network tasks run after yield | Reaches control accept task and repeated network poll heartbeats. |
| `08_dio0_dio1_matched_reachability` | Matched rebuild from JSON with only DIO EEM0 and EEM1 added | Reaches control accept task and repeated network poll heartbeats. |
| `09_dio0_dio1_sed_spread_enabled` | Same 2-DIO image as `08`, but re-enable `sed_spread_enable_write(0)` | Reaches network addresses, then stops at `diag: before SED spread CSR write value 0`; no `after` marker observed. |
| `10_dio0_dio1_rtio_csr_preflight` | Same 2-DIO image as `08`/`09`, skip SED spread again and add metadata-only RTIO CSR/clock preflight logs | Reaches RTIO preflight, skips SED/PHY reset, starts control/network tasks, reports 1 Gbit link, and heartbeats through at least 19.999962s. |
| `11_dio0_dio1_sys_crg_read_probe` | Same 2-DIO image as `10`, add one read-only SYS_CRG `current_clock_read()` before RTIO management startup | Reaches network addresses and `diag: before SYS_CRG current_clock_read probe`; no returned/after marker observed. |
| `12_dio0_dio1_forced_sys_clock_csr_probe` | Same 2-DIO image as `11`, but default the SYS_CRG clock-switch CSR high in gateware and use forced-SYS read breadcrumbs | Reaches network addresses and `diag: before forced-SYS SYS_CRG current_clock_read probe`; no returned/after marker observed. |
| `13_dio0_dio1_ps_fclk_sys_identifier_probe` | Clock PL `sys` from Zynq PS FCLK, remove standalone `sys_crg`, and run one explicit `identifier_read()` after networking | `identifier_read()` returns `9+unknown;13_dio0_dio1_ps_fclk_sys_identifier_probe`, RTIO metadata preflight runs with `has_sys_crg=false`, control/network tasks start, 1 Gbit link comes up, and heartbeats continue through at least 19.999962s. |
| `14_dio0_dio1_standalone_sys_crg_identifier_probe` | Restore standalone SYS_CRG/MMCM clocking while keeping SYS/RTIO clock-switch writes, SYS_CRG status reads, SED spread, RTIO PHY reset, analyzer startup, and async RTIO error reporting skipped; run only an explicit `identifier_read()` after networking | Reaches Si5324 lock, skipped SYS/RTIO switch, network addresses, and `diag: before standalone-SYS identifier_read CSR probe`; no returned/after marker observed. |
| `15_dio0_dio1_sys_crg_bootstrap_identifier_probe` | Keep standalone SYS_CRG present, but default its clock-switch CSR low so the MMCM stays on the bootstrap clock path; keep firmware clock switching skipped and run the same post-network `identifier_read()` | Built as `build/incremental_no_entangler/15_dio0_dio1_sys_crg_bootstrap_identifier_probe/boot.bin`; hardware result pending. |
| `16_dio0_dio1_bootstrap_sed_spread_probe` | Same two-DIO/no-Entangler/bootstrap-SYS setup as `15`, intended to run `identifier_read()` and then re-test `sed_spread_enable_write(0)` | Reaches network addresses and `diag: before bootstrap-SYS identifier_read CSR probe`; no returned/after marker observed, so the SED-spread write is not reached. |
| `17_dio0_dio1_bootstrap_sed_spread_no_ident_probe` | Same two-DIO/no-Entangler/bootstrap-SYS setup as `16`, but skip every `identifier_read()` so the first intentional post-network PL/RTIO CSR transaction is `sed_spread_enable_write(0)` | Reaches network addresses, RTIO CSR preflight, `SED spreading disabled by default`, and `diag: before bootstrap-SYS SED spread CSR write value 0 address=0x80001008`; no after-write marker observed. |
| `18_dio0_dio1_bootstrap_axi_csr_timeout_probe` | Same two-DIO/no-Entangler/bootstrap-SYS setup as `17`, add a bootstrap-clocked AXI2CSR response path and PL-side `csr_bridge_probe` observer intended to distinguish AXI response failure from target CSR-bank failure | Reaches network addresses, RTIO CSR preflight, and `SED spreading disabled by default`; no `experiment 18 bootstrap AXI/CSR probe armed` marker observed. This means the first blocking read of `csr_bridge_probe::sys_heartbeat_read()` at `0x80001800` hangs before the intended SED write is attempted. |
| `19_dio0_dio1_bootstrap_axi_write_only_probe` | Same two-DIO/no-Entangler/bootstrap-SYS setup as `18`, keep the bootstrap-clocked AXI2CSR path, and remove all post-network PL CSR reads before exactly one direct `sed_spread_enable_write(0)` | Reaches network addresses, RTIO CSR metadata preflight, `SED spreading disabled by default`, and `diag: before experiment 19 bootstrap AXI write-only SED spread CSR write value 0 address=0x80001008`; no after-write marker observed. This classifies the RTIO-core SED write as still not completing even with no earlier blocking reads and with bootstrap-clocked AXI2CSR. |
| `20_dio0_dio1_bootstrap_axi_local_write_sink_probe` | Same two-DIO/no-Entangler/bootstrap-SYS setup as `19`, but make the first post-network PL CSR transaction a write to a bootstrap-domain dummy `bootstrap_write_sink` instead of an RTIO-core CSR | Reaches network addresses, RTIO CSR metadata preflight, `SED spreading disabled by default`, and `diag: before experiment 20 bootstrap-local write sink CSR write value 0 address=0x80001800`; no after-write marker observed. This classifies the hang as broader than RTIO-core/sys-domain CSR targets: even a bootstrap-local dummy CSR write does not complete. |
| `21_dio0_dio1_ps_fclk_axi_local_write_sink_probe` | Remove standalone `SYS_CRG`, clock active PL `sys` from Zynq PS FCLK, keep normal AXI2CSR, and make the first post-network PL CSR transaction a write to a dummy `ps_fclk_write_sink` | Prints the before-write and after-write markers for `ps_fclk_write_sink::value_write(0)` at `0x80001000`, exits RTIO management, starts moninj/kernel-control/management/control accept tasks, reports 1 Gbit link-up, and continues network poll heartbeats. This disproves a universal generated CSR write failure and shifts suspicion back to standalone `SYS_CRG`/MMCM/reset integration, bootstrap clock-domain interactions, or the bootstrap AXI2CSR diagnostic wiring. |
| `22_dio0_dio1_standalone_sys_crg_normal_axi_local_write_sink_probe` | Restore standalone SYS_CRG/MMCM-driven `sys`, keep normal AXI2CSR, and make the first post-network PL CSR transaction a write to a dummy generated `standalone_sys_write_sink` | Reaches network addresses, RTIO CSR metadata preflight, `SED spreading disabled by default`, and `diag: before experiment 22 standalone-SYS local write sink CSR write value 0 address=0x80001800`; no after-write marker observed. This shows standalone SYS_CRG plus normal AXI2CSR is enough to break a dummy generated CSR write. |
| `23_dio0_dio1_standalone_sys_crg_bootstrap_input_normal_axi_local_write_sink_probe` | Keep standalone SYS_CRG and normal AXI2CSR, but force the SYS_CRG MMCM onto the bootstrap clock input before the same dummy generated `standalone_sys_write_sink` write | Reaches network addresses, RTIO CSR metadata preflight, `sys_crg_bootstrap_input_probe=true`, `SED spreading disabled by default`, and `diag: before experiment 23 standalone-SYS bootstrap-input local write sink CSR write value 0 address=0x80001800`; no after-write marker observed. This shifts suspicion away from the external/main CDR/SI5324 SYS_CRG input path and toward standalone SYS_CRG/MMCM/reset integration or AXI2CSR completion into standalone SYS_CRG-driven `sys`. |

## `18_dio0_dio1_bootstrap_axi_csr_timeout_probe` Boot Result

Artifact directory:

```text
build/incremental_no_entangler/18_dio0_dio1_bootstrap_axi_csr_timeout_probe/
```

Deployable image:

```text
build/incremental_no_entangler/18_dio0_dio1_bootstrap_axi_csr_timeout_probe/boot.bin
```

Build facts:

```text
boot.bin SHA256 = 51475589c9726299b3448fa313190f8211805eede83c23c2573cd3b3c223aecf
WNS = 0.601 ns
TNS = 0.000 ns
Route errors = 0
source.json hw_rev = v1.0
source.json peripherals = DIO EEM0, DIO EEM1 only
Entangler = absent
generated csr_bridge_probe base = 0x80001800
generated csr_bridge_probe sys_heartbeat = 0x80001800
generated rtio_core sed_spread_enable = 0x80001008
generated sys_crg_storage_full = 1'd0
```

The user-provided real Node v1.0 boot log reached:

```text
diag: skipping identifier_read for experiment 18 bootstrap AXI/CSR timeout probe
diag: skipping SYS/RTIO clock switch for populated-carrier test
network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 ...
diag: skipping async RTIO error reporter task
diag: before rtio_mgt startup
diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=0x80000800 rtio_core=0x80001000
diag: rtio csr preflight: generated CSR bases rtio=0x80002000 rtio_dma=0x80002800 rtio_moninj=0x80003800
diag: clock preflight: SYS/RTIO clock switch remains skipped in this diagnostic image
diag: before rtio_mgt setup_sed_spread
SED spreading disabled by default
```

No later marker was observed:

```text
diag: experiment 18 bootstrap AXI/CSR probe armed ...
diag: before experiment 18 AXI/CSR timeout-safe SED spread write ...
diag: after experiment 18 AXI/CSR timeout-safe SED spread write ...
```

Conclusion: experiment `18` did not test the intended timeout-safe SED-spread
write. It exposed another instance of the same trap: the firmware made ordinary
blocking CSR reads of the newly added `csr_bridge_probe` bank before attempting
the write. The first such read, `csr_bridge_probe::sys_heartbeat_read()` at
`0x80001800`, blocks on the real populated Node v1.0 carrier. The next image
must not perform any post-network blocking CSR reads before the decisive
transaction.

## Prompt For Experiment 19

```text
Continue the Kasli-SoC real Node v1.0 diagnostic ladder from experiment 18.

Current finding:
- Experiment 18 booted on the real populated Node v1.0 Kasli.
- It skipped all identifier_read() calls.
- It kept Entangler absent.
- It kept only DIO EEM0 and DIO EEM1.
- It kept standalone SYS_CRG present.
- It kept SYS_CRG clock_switch CSR default/reset low, with generated Verilog sys_crg_storage_full = 1'd0.
- It skipped firmware SYS/RTIO clock switching.
- It skipped async RTIO error reporter, analyzer startup, and RTIO PHY reset CSR write.
- It reached network addresses and the RTIO CSR metadata preflight.
- It reached:
  diag: before rtio_mgt setup_sed_spread
  SED spreading disabled by default
- It did not print:
  diag: experiment 18 bootstrap AXI/CSR probe armed ...
- Conclusion: experiment 18 accidentally made the first decisive operation another ordinary blocking CSR read. The read of csr_bridge_probe::sys_heartbeat_read() at 0x80001800 wedged before the intended timeout-safe sed_spread_enable_write(0) was attempted.

Design experiment 19.

Variant name:
19_dio0_dio1_bootstrap_axi_write_only_probe

Goal:
Avoid all post-network blocking CSR reads before the decisive transaction. Determine whether a bootstrap-clocked AXI2CSR response path lets the ARM/PS complete a write to the RTIO-core SED-spread CSR, and use only non-CSR evidence or later optional evidence to classify what happened.

Requirements:
- Target the real Node v1.0 Kasli, not the unpopulated v1.1 test Kasli.
- Every generated JSON must use "hw_rev": "v1.0".
- Keep Entangler absent.
- Do not add more EEM cards.
- Use the same minimal two-DIO JSON shape as experiments 13-18.
- Build and archive boot.bin, not only top.bit.
- Keep standalone SYS_CRG present.
- Keep SYS_CRG clock_switch CSR default/reset low so generated Verilog has sys_crg_storage_full = 1'd0.
- Keep firmware SYS/RTIO clock-switch write skipped.
- Keep all identifier_read() calls skipped.
- Keep async RTIO error reporter skipped.
- Keep analyzer startup skipped.
- Keep RTIO PHY reset CSR write skipped.

Implementation direction:
- Do not read csr_bridge_probe, sys_crg, identifier, rtio_core, rtio, rtio_dma, rtio_moninj, or any other PL CSR before the decisive write.
- Do not log any "probe armed" marker that depends on a CSR read.
- Print a UART marker immediately before the write.
- Perform exactly one direct write to csr::rtio_core::sed_spread_enable_write(0), using the experiment-18 bootstrap-clocked AXI2CSR response-path modification or an equivalent AXI response timeout/decoupling mechanism.
- Print a UART marker immediately after the write.
- Only after the after-write marker is printed may the firmware attempt optional diagnostic CSR reads, and those reads should either be omitted entirely or clearly marked as secondary and disposable.

Expected classification:
1. If the UART stops after the before-write marker, the ARM/PS AXI write still did not receive a response even with the bootstrap-clocked AXI2CSR path.
2. If the after-write marker prints, the ARM/PS AXI write completed; experiment 17's hang was in the normal sys-clocked AXI/CSR response path rather than in software after the write.
3. If optional post-write CSR reads hang, ignore that as a secondary result; the decisive experiment is whether the after-write marker prints.

Before building, explicitly verify:
1. Source JSON contains "hw_rev": "v1.0".
2. Artifact is intended for the real Node v1.0 Kasli.
3. No Entangler or extra EEM cards were added.
4. There is no post-network identifier_read().
5. There are no post-network CSR reads before the decisive sed_spread_enable_write(0).
6. The first decisive diagnostic cannot hard-block before the write because of a read-only CSR probe.

After building, archive source JSON, boot.bin, top.bit, runtime.elf/bin, pl.rs, rustc-cfg, mem.rs, timing report, route-status report, and manifest together. Report boot.bin path and SHA256 first, then timing WNS/TNS, route error count, and expected UART markers.
```

## `19_dio0_dio1_bootstrap_axi_write_only_probe` Boot Result

Artifact directory:

```text
build/incremental_no_entangler/19_dio0_dio1_bootstrap_axi_write_only_probe/
```

Deployable image:

```text
build/incremental_no_entangler/19_dio0_dio1_bootstrap_axi_write_only_probe/boot.bin
```

Build facts:

```text
boot.bin SHA256 = abd7250e2b19602df3110506ec67d52c4bd11caa542ce87f91c15b0b043b0313
WNS = 0.254 ns
TNS = 0.000 ns
Route errors = 0
source.json hw_rev = v1.0
source.json peripherals = DIO EEM0, DIO EEM1 only
Entangler = absent
generated csr_bridge_probe base = 0x80001800
generated rtio_core sed_spread_enable = 0x80001008
generated sys_crg_storage_full = 1'd0
rustc-cfg includes bootstrap_axi_csr_write_only_probe
```

The user-provided real Node v1.0 boot log reached:

```text
diag: skipping identifier_read for experiment 19 bootstrap AXI write-only probe
diag: skipping SYS/RTIO clock switch for populated-carrier test
network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 ...
diag: skipping async RTIO error reporter task
diag: skipping identifier_read for experiment 19 bootstrap AXI write-only probe
diag: before rtio_mgt startup
diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=0x80000800 rtio_core=0x80001000
diag: rtio csr preflight: generated CSR bases rtio=0x80002000 rtio_dma=0x80002800 rtio_moninj=0x80003800
diag: rtio csr preflight: rtio_core base=0x80001000 reset=0x80001000 reset_phy=0x80001004 sed_spread_enable=0x80001008
diag: rtio csr preflight: sys_crg base=0x80000800 current_clock=0x80000800 clock_switch=0x80000804
diag: clock preflight: SYS/RTIO clock switch remains skipped in this diagnostic image
diag: before rtio_mgt setup_sed_spread
SED spreading disabled by default
diag: experiment 19 write-only probe: no post-network PL CSR reads have been attempted before the decisive write
diag: before experiment 19 bootstrap AXI write-only SED spread CSR write value 0 address=0x80001008
```

No later marker was observed:

```text
diag: after experiment 19 bootstrap AXI write-only SED spread CSR write value 0
diag: experiment 19 classification: after-write marker printed, so the ARM/PS AXI write completed
diag: after rtio_mgt setup_sed_spread
```

Conclusion: experiment `19` did test the intended write-only operation. The
UART stops immediately after the before-write marker, so the ARM/PS AXI write
to `csr::rtio_core::sed_spread_enable_write(0)` still does not receive a
completion response even with the bootstrap-clocked AXI2CSR path and with no
post-network blocking CSR reads before the write.

This narrows the next question: is the failure in the generic PS AXI to
bootstrap-clocked CSR write path, or is it specific to the RTIO-core/sys-domain
CSR target? The next image should make the first post-network CSR transaction a
write to a bootstrap-local dummy CSR sink that does not depend on RTIO-core,
SYS_CRG, identifier, or any sys-domain target. Only after that local write
returns should it optionally attempt the RTIO-core SED write as a secondary
comparison.

## Prompt For Experiment 20

```text
Continue the Kasli-SoC real Node v1.0 diagnostic ladder from experiment 19.

Current finding:
- Experiment 19 booted on the real populated Node v1.0 Kasli.
- It skipped identifier_read(), Entangler, SYS/RTIO clock switching, async RTIO error reporter, analyzer startup, and RTIO PHY reset CSR write.
- It kept only DIO EEM0 and DIO EEM1.
- It kept standalone SYS_CRG present with clock_switch reset/default low; generated Verilog had sys_crg_storage_full = 1'd0.
- It kept the experiment-18/19 bootstrap-clocked AXI2CSR response-path modification.
- It performed no post-network PL CSR reads before the decisive write.
- It reached network addresses, RTIO CSR metadata preflight, `diag: before rtio_mgt setup_sed_spread`, `SED spreading disabled by default`, and:
  `diag: before experiment 19 bootstrap AXI write-only SED spread CSR write value 0 address=0x80001008`
- It did not print:
  `diag: after experiment 19 bootstrap AXI write-only SED spread CSR write value 0`
- Conclusion: the ARM/PS AXI write to the RTIO-core SED-spread CSR still did not receive a completion response even when no earlier post-network CSR reads occurred and AXI2CSR was clocked from the bootstrap clock.

Design experiment 20.

Variant name:
20_dio0_dio1_bootstrap_axi_local_write_sink_probe

Goal:
Separate a generic PS AXI -> bootstrap-clocked CSR write-response failure from an RTIO-core/sys-domain CSR target failure. Make the first post-network PL CSR transaction a write to a bootstrap-local dummy CSR sink that has no RTIO-core, SYS_CRG, identifier, rtio, rtio_dma, rtio_moninj, or sys-domain target dependency.

Requirements:
- Target the real Node v1.0 Kasli; every generated JSON must use `"hw_rev": "v1.0"`.
- Keep Entangler absent.
- Keep only DIO EEM0 and DIO EEM1.
- Build and archive `boot.bin`, not only `top.bit`.
- Keep standalone SYS_CRG present and keep clock_switch reset/default low so generated Verilog still has `sys_crg_storage_full = 1'd0`.
- Keep firmware SYS/RTIO clock-switch write skipped.
- Keep all `identifier_read()` calls skipped.
- Keep async RTIO error reporter skipped.
- Keep analyzer startup skipped.
- Keep RTIO PHY reset CSR write skipped.
- Keep the bootstrap-clocked AXI2CSR path from experiments 18 and 19.

Implementation direction:
- Add a minimal bootstrap-clocked local CSR write sink, for example `bootstrap_write_sink`, with a CSRStorage or equivalent write-only register in the bootstrap clock domain.
- The sink must not depend on or cross into `sys`, RTIO-core, SYS_CRG, identifier, rtio, rtio_dma, rtio_moninj, analyzer, or csr_bridge_probe logic for its write completion.
- Do not read `csr_bridge_probe`, `bootstrap_write_sink`, `sys_crg`, `identifier`, `rtio_core`, `rtio`, `rtio_dma`, `rtio_moninj`, or any other PL CSR before the decisive local write.
- Print a UART marker immediately before the local write.
- Perform exactly one direct write to the bootstrap-local CSR sink.
- Print a UART marker immediately after the local write.
- Only after the after-local-write marker prints may the firmware attempt a secondary RTIO-core SED write. If included, clearly mark it secondary:
  - print a UART marker immediately before `csr::rtio_core::sed_spread_enable_write(0)`
  - perform exactly one direct `csr::rtio_core::sed_spread_enable_write(0)`
  - print a UART marker immediately after it
- Do not perform optional CSR reads at all in this experiment unless they occur after all write markers and are clearly marked disposable.

Classification:
1. Stops after the before-local-write marker: even a bootstrap-local CSR write does not complete; suspect the generic PS AXI/AXI2CSR write-response path or the bootstrap CSR write path itself.
2. Prints the after-local-write marker, then stops after the secondary before-RTIO-write marker: the bootstrap AXI2CSR path can complete local writes; the hang is specific to the RTIO-core/sys-domain CSR target path.
3. Prints both after-write markers: both local and RTIO-core writes completed in this variant; compare generated CSR ordering/addresses and gateware changes against experiment 19.
4. Any optional post-write CSR read hang is secondary and must not change the decisive classification.

Before building, explicitly verify:
1. Source JSON contains `"hw_rev": "v1.0"`.
2. Artifact is intended for the real Node v1.0 Kasli.
3. No Entangler or extra EEM cards were added.
4. There is no post-network `identifier_read()`.
5. There are no post-network CSR reads before the decisive bootstrap-local write.
6. The first decisive diagnostic cannot hard-block before the local write because of a read-only CSR probe.
7. Generated `rustc-cfg` exposes the experiment-20 write-sink feature and the generated `pl.rs` contains the bootstrap-local CSR sink address.

After building, archive source JSON, boot.bin, top.bit, runtime.elf/bin, pl.rs, rustc-cfg, mem.rs, timing report, route-status report, and manifest together. Report boot.bin path and SHA256 first, then WNS/TNS, route error count, generated sink address, generated RTIO-core SED address, and expected UART markers.
```

## `08_dio0_dio1_matched_reachability` Artifact

This image was built after adding the CSR-provenance guardrails. It uses only
the two DIO cards:

```text
build/generated/incremental_no_entangler_02_dio0_dio1.json
```

Artifact directory:

```text
build/incremental_no_entangler/08_dio0_dio1_matched_reachability/
```

Deployable image:

```text
build/incremental_no_entangler/08_dio0_dio1_matched_reachability/boot.bin
```

Hashes:

```text
1d2b944d4e8dd69fbe1c56863153a886464a6b2a7748e3c744692156ae21955d  boot.bin
0c05468cd0cdfe4d378d2c0f75b116152d014d5ebf0abdbf3d0ce49eb208b005  top.bit
e461117077448beef6acd6365e321afd35dae2caf43fb36d794bc5f92d213a46  runtime.bin
```

Vivado met timing:

```text
WNS = 0.282 ns
TNS = 0.000 ns
Route errors = 0
```

The build includes the current diagnostic runtime edits, so this is a
reachability test image rather than a clean production runtime.

Boot log result:

```text
ai/boot_log_08_dio0_dio1_matched_reachability_2026-05-27.md
```

The user-provided boot log shows this image reaching `network addresses` with
IPv4 `192.168.1.75`, starting the control accept task, reporting a 1 Gbit
full-duplex Ethernet link, and continuing to print network poll heartbeats
through at least 44.999912 seconds.

## `09_dio0_dio1_sed_spread_enabled` Artifact

This image keeps the same 2-DIO JSON as `08`, but re-enables the RTIO management
SED spread CSR write:

```text
csr::rtio_core::sed_spread_enable_write(0)
```

Artifact directory:

```text
build/incremental_no_entangler/09_dio0_dio1_sed_spread_enabled/
```

Deployable image:

```text
build/incremental_no_entangler/09_dio0_dio1_sed_spread_enabled/boot.bin
```

Hashes:

```text
340b37ce590a42f42d1ee10c33d16d1e5121048e7e6bbadc14d2b316c1acecd5  boot.bin
30281e471745442c983e706f6229aaf6a744dfac632d2c4eec85242b84bbe737  top.bit
fb221aa66f4a55372556dd62532e865193a4b5547816c3dbd4a36276bf7bb9f6  runtime.bin
```

Vivado met timing:

```text
WNS = 0.282 ns
TNS = 0.000 ns
Route errors = 0
```

Expected decisive boot markers:

```text
diag: before SED spread CSR write value 0
diag: after SED spread CSR write value 0
```

If the populated-node boot log reaches the `after` marker, the SED spread CSR
write is not the blocker for this 2-DIO gateware. The next diagnostic step would
be to re-enable the RTIO PHY reset CSR write while keeping the other skips.

Boot log result:

```text
ai/boot_log_09_dio0_dio1_sed_spread_enabled_2026-05-27.md
```

The user-provided boot log shows this image reaching runtime startup, I2C, both
I/O expanders, Si5324 lock, skipped SYS/RTIO clock switch, and network address
assignment at IPv4 `192.168.1.75`. It then enters `rtio_mgt::startup()` and
prints:

```text
diag: before SED spread CSR write value 0
```

No matching `diag: after SED spread CSR write value 0` marker was observed.
This confirms the immediate stop is at
`csr::rtio_core::sed_spread_enable_write(0)` for the 2-DIO populated-carrier
diagnostic image. The next step should not be to re-enable
`rtio_core::reset_phy_write(1)` yet; the next image should skip the SED spread
write again and collect targeted CSR/clock-domain evidence before attempting
another RTIO-core write.

## `10_dio0_dio1_rtio_csr_preflight` Artifact

This image keeps the same 2-DIO JSON as `08` and `09`, skips the SED spread CSR
write again, and adds metadata-only RTIO CSR and clock preflight logs before
RTIO management setup. The new logs do not read or write the RTIO-core CSR
window; they report generated addresses and compile-time configuration.

Artifact directory:

```text
build/incremental_no_entangler/10_dio0_dio1_rtio_csr_preflight/
```

Deployable image:

```text
build/incremental_no_entangler/10_dio0_dio1_rtio_csr_preflight/boot.bin
```

Hashes:

```text
aa265fb8888d48c94d641180d62ca591a000b96aecb91ea25aaecc0143c70e3a  boot.bin
79728f050f9690913776b1aa6fd2fbb1e448ef669423edb38c19aae47c449ea5  top.bit
6f5ff2cf0142be97c10ccb7c628ee99ab0ac56186f4504ee6c2e1e5d451bf104  runtime.bin
920bcce20c236ef7b9ac5cbed9de9a19deaa8632626116befc253c3af4267494  runtime.elf
```

Generated metadata hashes:

```text
c569db1bc14763b25ae008520b11a4d429f42a9714281c7eb323fb9223ef13a7  pl.rs
eaca1744efa148a9172e8c1577fbe7d1e6bfc334fd53e184d45fd6ac89fb8591  rustc-cfg
95c24a456947f79c8f531b00e60313f75131b850a630c12650b5bfae32ab9265  mem.rs
```

Vivado met timing:

```text
WNS = 0.282 ns
TNS = 0.000 ns
Route errors = 0
```

Expected new boot markers:

```text
diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=0x80000800 rtio_core=0x80001000
diag: rtio csr preflight: generated CSR bases rtio=0x80001800 rtio_dma=0x80002000 rtio_moninj=0x80003000
diag: rtio csr preflight: rtio_core base=0x80001000 reset=0x80001000 reset_phy=0x80001004 sed_spread_enable=0x80001008
diag: rtio csr preflight: rtio_core sizes reset=1 reset_phy=1 sed_spread_enable=1
diag: rtio csr preflight: sys_crg base=0x80000800 current_clock=0x80000800 clock_switch=0x80000804
diag: rtio csr preflight: runtime cfg has_rtio_core=true
diag: rtio csr preflight: runtime cfg has_sys_crg=true
diag: clock preflight: generated rtio_frequency=125.0 MHz
diag: clock preflight: generated clock_frequency=125000000 Hz
diag: clock preflight: generated config has_si5324=true
diag: clock preflight: SYS/RTIO clock switch remains skipped in this diagnostic image
SED spreading disabled by default
diag: skipping SED spread CSR write value 0 after 09 populated-carrier hang
diag: after rtio_mgt setup_sed_spread
```

The `10` build is intended to restore the reachable `08` behavior while
capturing generated RTIO-core/SYS_CRG metadata. If it reaches
`diag: after rtio_mgt startup` and the later network/control-loop markers, the
metadata has been captured without touching the first known-hanging RTIO-core
write.

Boot log result:

```text
ai/boot_log_10_dio0_dio1_rtio_csr_preflight_2026-05-27.md
```

The user-provided boot log shows the expected preflight markers printing
completely, including the generated CSR bases:

```text
identifier=0x80000000
sys_crg=0x80000800
rtio_core=0x80001000
rtio=0x80001800
rtio_dma=0x80002000
rtio_moninj=0x80003000
sed_spread_enable=0x80001008
```

The runtime then skips the SED spread CSR write, skips RTIO PHY reset, reaches
`diag: after rtio_mgt startup`, starts moninj, kernel control, management, and
the control accept task, enters the network poll loop, reports 1 Gbit full
duplex Ethernet, and prints network poll heartbeats through at least
`19.999962s`.

This confirms that metadata-only RTIO CSR/SYS_CRG reporting is safe on the
populated carrier and that the `09` failure remains tied to executing the
RTIO-core SED spread CSR write rather than to the generated CSR address metadata
itself. The missing `device_map` warning appears after RTIO management startup
and is not the current boot blocker.

## `11_dio0_dio1_sys_crg_read_probe` Artifact

This image keeps the same 2-DIO JSON as `08`, `09`, and `10`, keeps all of the
successful test `10` skips, and adds one read-only SYS_CRG current-clock CSR
read immediately before RTIO management startup.

Artifact directory:

```text
build/incremental_no_entangler/11_dio0_dio1_sys_crg_read_probe/
```

Deployable image:

```text
build/incremental_no_entangler/11_dio0_dio1_sys_crg_read_probe/boot.bin
```

Hashes:

```text
f72674ce07da0952740a0e4f04cab4757185f6d3104bd150212b7383509f3764  boot.bin
d47010f63a1097bba4c578135ad56b69527be0a88e91928767adc0f8ee838a72  top.bit
c845db4e9a4230cbb73cc2e6822581f94c68cfac14a4032b48068fe124de8c25  runtime.elf
```

Expected decisive markers:

```text
diag: before SYS_CRG current_clock_read probe
diag: SYS_CRG current_clock_read returned <value>
diag: after SYS_CRG current_clock_read probe
```

Boot log result:

```text
ai/boot_log_11_dio0_dio1_sys_crg_read_probe_2026-05-27.md
```

The user-provided boot log shows this image reaching runtime startup, I2C, both
I/O expanders, Si5324 lock, skipped SYS/RTIO clock switch, and network address
assignment at IPv4 `192.168.1.75`. It then prints:

```text
diag: before SYS_CRG current_clock_read probe
```

No matching `SYS_CRG current_clock_read returned` marker was observed. This
confirms that a read-only SYS_CRG status CSR access hangs on the populated
carrier when executed after the skipped SYS/RTIO clock-switch path. The finding
is broader than RTIO-core writes.

## `12_dio0_dio1_forced_sys_clock_csr_probe` Artifact

This image keeps the same 2-DIO JSON as `08`, `09`, `10`, and `11`, keeps all
of the successful test `10`/`11` firmware skips, and makes one gateware-side
clock-selection change: the standalone SYS_CRG `clock_switch` CSR storage now
resets high, so the SYS_CRG clock-switch FSM defaults toward the
post-Si5324/main SYS clock path without a firmware
`sys_crg::clock_switch_write(1)` transaction.

Artifact directory:

```text
build/incremental_no_entangler/12_dio0_dio1_forced_sys_clock_csr_probe/
```

Deployable image:

```text
build/incremental_no_entangler/12_dio0_dio1_forced_sys_clock_csr_probe/boot.bin
```

Hashes:

```text
30550f50ee757705f5cd2ec69d188f0c1402ffebea50bbbd17693eedd12b5ebf  boot.bin
7c90856e236eb9a5dd28f8eecb85065d2bdf999a4a3a983b1dcf5c22cfa36574  top.bit
64bc0e84a67e96e5a763d5ee8232532ce45fc5e2b96585b04a8fe21b713c3d13  runtime.elf
d5a27aa99b29746dd9648bb5b14968baab58d563c9628c89417d18517a1faf31  runtime.bin
f935b5a83a5e1c3d0baa027062278e319963e3525188d49a93a8c6ebc8026921  source JSON
```

Vivado completed route and bitstream generation successfully. The final timing
report shows WNS `0.282 ns` and `All user specified timing constraints are
met.` The route-status report shows `0` nets with routing errors. The DRC report
contains warning-only results: 8 `BUFC-1`, 1 `LVDS-1`, and 1 `RTSTAT-10`.

Generated-gateware confirmation:

```text
reg sys_crg_storage_full = 1'd1;
```

Expected decisive markers:

```text
diag: before forced-SYS SYS_CRG current_clock_read probe
diag: forced-SYS SYS_CRG current_clock_read returned <value>
diag: after forced-SYS SYS_CRG current_clock_read probe
diag: before rtio_mgt startup
```

Boot log result:

```text
ai/boot_log_12_dio0_dio1_forced_sys_clock_csr_probe_2026-05-27.md
```

Observed populated-carrier result:

```text
[     2.652919s]  INFO(runtime::comms): diag: skipping async RTIO error reporter task
[     2.654757s]  INFO(runtime::comms): diag: before forced-SYS SYS_CRG current_clock_read probe
```

No matching return or post-probe marker was observed:

```text
diag: forced-SYS SYS_CRG current_clock_read returned <value>
diag: after forced-SYS SYS_CRG current_clock_read probe
diag: before rtio_mgt startup
```

Interpretation:

- The read still hangs, so the issue is not just the skipped firmware SYS/RTIO
  clock switch; PS-to-PL CSR access is still unresponsive even with SYS clock
  selection forced/defaulted in gateware.
- Do not advance to RTIO-core write probes yet. The next diagnostic branch
  should stay focused on why actual PL CSR transactions can hang after
  otherwise successful runtime/network bring-up.

## Current Diagnostic Patch Scope

The diagnostic runtime currently differs from upstream runtime behavior in these
ways:

- `main.rs` skips `identifier_read()` and logs early boot checkpoints.
- `rtio_clocking.rs` skips the standalone `init_rtio()` SYS/RTIO clock switch.
- `rtio_mgt.rs` logs generated RTIO-core/SYS_CRG metadata, skips the SED spread
  CSR write again for the `10` test, and skips the RTIO PHY reset CSR write.
- `comms.rs` logs checkpoints around RTIO management, device-map setup,
  analyzer start, moninj start, kernel-control startup, management startup,
  control accept task startup, the test `12` forced-SYS SYS_CRG current-clock
  read probe, and the network poll loop.
- `zynq_clocking.py` defaults standalone SYS_CRG `clock_switch` storage to
  `1`, making the clock switch gateware-driven for test `12`.

These changes are diagnostics only. They are not a production fix because they
avoid RTIO initialization steps required for a normally functioning ARTIQ system.

## Current Finding After Test 12

The `12_dio0_dio1_forced_sys_clock_csr_probe` populated-carrier test stopped
during the same read-only SYS_CRG `current_clock_read()` probe even after the
SYS_CRG clock-switch selection was forced/defaulted high in gateware. Do not
advance to `rtio_core::reset_phy_write(1)` or other RTIO-core write probes yet.
The problem is now broader than RTIO-core writes and not explained solely by the
skipped firmware SYS/RTIO clock-switch transaction.

Test `12` kept the test `10`/`11` runtime skips intact:

- skip `identifier_read()` except at an explicit probe point,
- skip firmware SYS/RTIO clock switching,
- skip `sed_spread_enable_write(0)`,
- skip `reset_phy_write(1)`,
- skip analyzer,
- skip the async RTIO error reporter.

The single new variable was a gateware-side SYS clock selection change, not
another firmware CSR write: SYS_CRG clock-switch storage resets high, forcing or
defaulting the SYS_CRG clock switch selection to the post-Si5324/main SYS clock
path for this diagnostic image. The firmware then ran the same single read-only
SYS_CRG current-clock probe before RTIO management startup.

Expected markers:

```text
diag: before forced-SYS SYS_CRG current_clock_read probe
diag: forced-SYS SYS_CRG current_clock_read returned <value>
diag: after forced-SYS SYS_CRG current_clock_read probe
diag: before rtio_mgt startup
```

Interpretation:

- The read still hangs, so the problem is not just that the firmware SYS/RTIO
  clock switch was skipped; the PS-to-PL CSR path is still unresponsive with the
  SYS clock source forced in gateware.
- The next branch should investigate PL CSR bus responsiveness, reset/clock
  domain readiness, or CSR timeout instrumentation before adding any RTIO-core
  writes back to the path.

## Current Finding After Test 13

The `13_dio0_dio1_ps_fclk_sys_identifier_probe` populated-carrier test changed
the conclusion. It clocked the PL `sys` fabric directly from Zynq PS FCLK,
removed the standalone `sys_crg` CSR block, did not generate Si5324/Si549
clock-synthesizer config, and then ran one real `identifier_read()` after
network setup.

The read returned successfully:

```text
[     0.324758s]  INFO(runtime::comms): diag: before PS-FCLK identifier_read CSR probe
[     0.332332s]  INFO(runtime::comms): diag: PS-FCLK identifier_read returned 9+unknown;13_dio0_dio1_ps_fclk_sys_identifier_probe
[     0.343681s]  INFO(runtime::comms): diag: after PS-FCLK identifier_read CSR probe
```

The runtime then continued through RTIO metadata-only preflight, management and
control startup, Ethernet link-up, and repeated network heartbeats:

```text
[     0.357222s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=absent rtio_core=0x80000800
[     0.416419s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: runtime cfg has_sys_crg=false
[     0.598700s]  INFO(runtime::comms): diag: after control accept task spawn
[     3.619096s]  INFO(libboard_zynq::eth): eth: got Link { speed: S1000, duplex: Full }
[    19.999962s]  INFO(runtime::comms): diag: network poll heartbeat
```

Interpretation:

- The populated-carrier problem is not a universal AXI/PS-to-PL CSR bridge
  failure. The identifier CSR can respond in the PS-FCLK-driven diagnostic
  image.
- The basic BOOT image packaging, SD loading path, runtime entry, networking,
  I2C, I/O expanders, management/control task startup, and identifier CSR block
  are all proven reachable in this diagnostic configuration.
- The stronger suspect is now the original standalone SYS_CRG/MMCM/reset/clock
  domain integration, or CSR transactions that depend on that generated
  SYS_CRG/RTIO fabric.
- The next experiment should reintroduce original standalone clocking pieces
  incrementally or add timeout/response instrumentation around SYS_CRG/RTIO CSR
  access. Broad rebuilds are unlikely to add useful information.

For any reachable diagnostic image such as `08`, host-side reachability can be
checked from a machine/interface on the board's `192.168.1.0/24` network:

```bash
ping -c 3 192.168.1.75
nc -vz 192.168.1.75 1380
nc -vz 192.168.1.75 1381
nc -vz 192.168.1.75 1382
nc -vz 192.168.1.75 1383
```

Interpretation:

- Port `1381` open means the main ARTIQ control accept task is listening.
- Port `1380` open means management service startup is reachable.
- Port `1383` open means moninj is reachable.
- Port `1382` is expected to be unavailable in `07` because analyzer startup is
  intentionally skipped.

If host reachability works, Ethernet/control service bring-up is no longer the
main blocker. The remaining production-relevant failure is the RTIO-facing CSR
startup path: identifier CSR, SYS/RTIO clock switch, SED spread/reset PHY, async
RTIO error polling, and analyzer arming.

The current workspace host is not on the same subnet. Its route to the board IP
is:

```text
192.168.1.75 via 192.168.12.2 dev ens33 src 192.168.12.128
```

When the board was powered back on with `07`, host-side reachability from this
workspace succeeded despite that route:

```text
ping -c 3 -W 1 192.168.1.75
3 packets transmitted, 3 received, 0% packet loss

port 1380 open
port 1381 open
port 1382 closed
port 1383 open
```

This confirms that the diagnostic `07` runtime is reachable over the network.
The closed `1382` analyzer port is expected because `07` intentionally skips
analyzer startup. Open `1380`, `1381`, and `1383` confirm that management,
control, and moninj service startup are reachable.

## Observation

- The `incremental_no_entangler_00_empty` image has no EEM peripherals in the
  ARTIQ system description:
  `build/generated/incremental_no_entangler_00_empty.json`.
- User hardware test result: the same empty/no-EEM image boots on the Kasli-SoC
  carrier with no cards attached, but does not boot on the populated Kasli-SoC
  carrier.

## Interpretation

This narrows the failure away from the generated EEM peripheral list, Entangler
integration, and RTIO channel count. Since the image has `"peripherals": []`,
the populated-board-only failure is more likely in early board/runtime startup
or in physical side effects of the attached cards.

The known UART anchor from the prior failing image was:

```text
NAR3/Zynq7000 starting...
```

In `repos/madmax-artiq-zynq/src/runtime/src/main.rs`, that print occurs before:

- heap allocator initialization
- GIC interrupt enable
- PL CSR `identifier_read`
- I2C initialization
- Kasli I/O expander initialization
- EEM power enable for `hw_rev = "v1.2"`
- RTIO clocking
- network address logging

Therefore, if the populated board still stops immediately after
`NAR3/Zynq7000 starting...`, the failure is earlier than RTIO clocking and
earlier than networking.

## `00_empty` Baseline Artifact

The baseline no-EEM image is:

```text
build/incremental_no_entangler/00_empty/boot.bin
```

It was built from:

```text
build/generated/incremental_no_entangler_00_empty.json
```

with no peripherals:

```json
"peripherals": []
```

Hashes:

```text
e9fca130165f57ba648b9c629198778b2ac41e5454944535aa5f87705c52b1d2  boot.bin
96b676623edd4e96acee1a1ec398c6d60242941ab1963a4e7e57ae50f8de1ab6  runtime.bin
b9f25f25d12a7cf0174fe6b9e3c12e4f8fbc816ce709188b12554d92769d4545  top.bit
```

## `01_empty_startup_diag` Diagnostic Artifact

A new diagnostic runtime was built against the same no-EEM JSON and packaged
with the same no-EEM bitstream. It adds UART checkpoints around the early
startup steps listed above.

Artifact directory:

```text
build/incremental_no_entangler/01_empty_startup_diag/
```

Deployable image:

```text
build/incremental_no_entangler/01_empty_startup_diag/boot.bin
```

Hashes:

```text
d55c8ec64d94759aadc587e834a33093fcc83023a564709e1dce2c4a716b97e0  boot.bin
e80d68da214d9e365df527b2b2744e98c0e444d2ab27ba020d1456ba554da9d6  runtime.bin
b9f25f25d12a7cf0174fe6b9e3c12e4f8fbc816ce709188b12554d92769d4545  top.bit
fc8390bcec799d510d0d8b83209b39cbadba15474a77f9a91768767ec604ce88  runtime.elf
87e904f0db263232bc99802d71cb1c59e46fe96b2a878158a603518724b81de8  szl.elf
```

## Expected UART Breadcrumbs

The next populated-carrier boot test should record the last line printed from
this sequence:

```text
diag: before ram init
diag: after ram init
diag: before gic enable
diag: after gic enable
diag: before identifier_read
gateware ident: ...
diag: after identifier_read
diag: before i2c init
diag: after i2c init
diag: before io expander construct
diag: after io expander construct
diag: before io expander init 0
diag: after io expander init 0
diag: before io expander init 1
diag: after io expander init 1
diag: before eem power enable
diag: after eem power enable
diag: before io expander service 0
diag: after io expander service 0
diag: before io expander service 1
diag: after io expander service 1
```

The last printed breadcrumb determines the next branch:

- Stops before or during `identifier_read`: investigate PL CSR access and
  early runtime startup before I2C/RTIO/networking.
- Stops during `i2c init` or I/O expander initialization: investigate Kasli I2C
  bus interaction with populated carrier hardware.
- Stops at or after `eem power enable`: investigate attached card power draw,
  EEM power rail faults, or a card pulling a rail/bus into an invalid state.
- Reaches `rtio_clocking::init()` but not network addresses: return to RTIO
  clock-source bring-up.

## Populated-Carrier Result From `01_empty_startup_diag`

The populated-carrier UART log reached:

```text
INFO(runtime): NAR3/Zynq7000 starting...
INFO(runtime): diag: before ram init
INFO(runtime): diag: after ram init
INFO(runtime): diag: before gic enable
INFO(runtime): diag: after gic enable
INFO(runtime): diag: before identifier_read
```

It did not print `gateware ident`, so the stop occurs inside
`libboard_artiq::identifier_read`, at the first runtime access to the PL CSR
identifier block. This confirms that the failure is before I2C initialization,
before RTIO clocking, and before network setup.

## Skip-Identifier Diagnostic Artifact

The next diagnostic image keeps the same no-EEM bitstream but skips only the
`identifier_read` call, leaving the rest of the early startup checkpoints in
place.

Artifact directory:

```text
build/incremental_no_entangler/02_empty_skip_ident/
```

Deployable image:

```text
build/incremental_no_entangler/02_empty_skip_ident/boot.bin
```

Hashes:

```text
05e49b20e10e7630edf7ba299acc394d95b9505123fecbb26d6e8ed4fcd4d4aa  boot.bin
15b738d252ad395385f874edb11d0ad34c1785d8a18dca195046875c4bc15ba7  runtime.bin
b9f25f25d12a7cf0174fe6b9e3c12e4f8fbc816ce709188b12554d92769d4545  top.bit
85aba7cf8b89b05fbda18727720956230db94b126ba1ac1371cd3cbe8a77759c  runtime.elf
87e904f0db263232bc99802d71cb1c59e46fe96b2a878158a603518724b81de8  szl.elf
```

Expected new marker:

```text
diag: skipping identifier_read for populated-carrier CSR hang test
```

If this image continues into I2C and later runtime stages, the identifier CSR
read itself is the immediate populated-carrier trigger. If it hangs later at
another PL/RTIO access, the problem is broader PL CSR access on the populated
carrier.

## Populated-Carrier Result From `02_empty_skip_ident`

The populated-carrier UART log reached:

```text
INFO(runtime): diag: skipping identifier_read for populated-carrier CSR hang test
INFO(runtime): diag: before i2c init
INFO(libboard_zynq::i2c): PCA9548 detected
INFO(runtime): diag: after i2c init
INFO(runtime): diag: before io expander construct
INFO(runtime): diag: after io expander construct
INFO(runtime): diag: before io expander init 0
INFO(runtime): diag: after io expander init 0
INFO(runtime): diag: before io expander init 1
INFO(runtime): diag: after io expander init 1
INFO(runtime): diag: before io expander service 0
INFO(runtime): diag: after io expander service 0
INFO(runtime): diag: before io expander service 1
INFO(runtime): diag: after io expander service 1
INFO(runtime): log level set to INFO by default
INFO(runtime): UART log level set to INFO by default
INFO(runtime::rtio_clocking): using 125MHz reference to make 125MHz RTIO clock with PLL
INFO(libboard_artiq::si5324): waiting for Si5324 lock...
INFO(libboard_artiq::si5324):   ...locked
INFO(runtime::rtio_clocking): Switching SYS clocks...
```

The image did not reach `network addresses`. With `identifier_read` skipped,
the next observed stop is in `runtime::rtio_clocking::init()`, immediately after
the Si5324 locks and the runtime writes the SYS clock switch CSR:

```rust
pl::csr::sys_crg::clock_switch_write(1);
```

This confirms that the populated-carrier boot has at least two PL/CSR-sensitive
failure points: the identifier CSR read and the SYS/RTIO clock switch.

## Skip-Identifier And Skip-RTIO-Switch Diagnostic Artifact

The next diagnostic image keeps the same no-EEM bitstream, skips
`identifier_read`, and bypasses the `init_rtio()` SYS/RTIO clock switch. It is
intended to test whether the runtime can reach network bring-up when the two
known failing PL/CSR operations are avoided.

Artifact directory:

```text
build/incremental_no_entangler/03_empty_skip_ident_skip_rtio_clock_switch/
```

Deployable image:

```text
build/incremental_no_entangler/03_empty_skip_ident_skip_rtio_clock_switch/boot.bin
```

Hashes:

```text
8947f8d555cf3822e12153af7bbb8c6f58375c238a02e70a20fdd39272ea1e0e  boot.bin
56d2ec54ab164845d08be9737c1c1f804c9121b2f0059f9e5906dca978bf790c  runtime.bin
b9f25f25d12a7cf0174fe6b9e3c12e4f8fbc816ce709188b12554d92769d4545  top.bit
6bc6851ecc78a582d2d5f20e2eaa58e8c9718a454941126c14b86ce4c30f995b  runtime.elf
87e904f0db263232bc99802d71cb1c59e46fe96b2a878158a603518724b81de8  szl.elf
```

Expected markers:

```text
diag: before rtio_clocking init
diag: skipping SYS/RTIO clock switch for populated-carrier test
diag: after rtio_clocking init
network addresses: ...
```

If this reaches `network addresses`, then the populated carrier can boot far
enough for Ethernet when the identifier CSR read and SYS clock switch are both
avoided.

## Populated-Carrier Result From `03_empty_skip_ident_skip_rtio_clock_switch`

The populated-carrier UART log reached:

```text
INFO(runtime): diag: before rtio_clocking init
INFO(runtime::rtio_clocking): using 125MHz reference to make 125MHz RTIO clock with PLL
INFO(libboard_artiq::si5324): waiting for Si5324 lock...
INFO(libboard_artiq::si5324):   ...locked
INFO(runtime::rtio_clocking): diag: skipping SYS/RTIO clock switch for populated-carrier test
INFO(runtime): diag: after rtio_clocking init
INFO(libboard_zynq::i2c): PCA9548 detected
INFO(runtime::comms): network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
INFO(runtime::rtio_mgt): SED spreading disabled by default
```

This confirms that Ethernet setup is reachable on the populated carrier when
the identifier CSR read and SYS/RTIO clock switch are skipped. The next observed
stop is immediately after `SED spreading disabled by default`, before any later
runtime services print diagnostics. In `rtio_mgt::setup_sed_spread()`, that log
is followed by:

```rust
csr::rtio_core::sed_spread_enable_write(0);
```

The following `rtio_mgt::startup()` path also writes:

```rust
csr::rtio_core::reset_phy_write(1);
```

So the next diagnostic skips those RTIO-core CSR writes as well.

## Skip-Identifier And Skip-RTIO-CSR Diagnostic Artifact

The next diagnostic image keeps the same no-EEM bitstream and skips:

- `identifier_read`
- SYS/RTIO clock switch in `rtio_clocking::init()`
- `rtio_core::sed_spread_enable_write`
- `rtio_core::reset_phy_write` in `rtio_mgt::startup()`

It also adds breadcrumbs around the remainder of `comms::main()` startup.

Artifact directory:

```text
build/incremental_no_entangler/04_empty_skip_ident_skip_rtio_csrs/
```

Deployable image:

```text
build/incremental_no_entangler/04_empty_skip_ident_skip_rtio_csrs/boot.bin
```

Hashes:

```text
254540077a6dc568f8d4d522b86cceb0eafa76d782adfc7b593acc97de6da101  boot.bin
557fd3cd9f880071faaef0419ceb51298d730e64075fe02c8c9b0df9bff277e9  runtime.bin
b9f25f25d12a7cf0174fe6b9e3c12e4f8fbc816ce709188b12554d92769d4545  top.bit
8defde8b3a23898c3e932e1e6652f2682dfc3e43855a456f24eb324619c85e31  runtime.elf
87e904f0db263232bc99802d71cb1c59e46fe96b2a878158a603518724b81de8  szl.elf
```

Expected markers after `network addresses`:

```text
diag: before rtio_mgt startup
diag: before rtio_mgt setup_sed_spread
SED spreading disabled by default
diag: skipping SED spread CSR write value 0
diag: after rtio_mgt setup_sed_spread
diag: before rtio_mgt drtio startup
diag: after rtio_mgt drtio startup
diag: skipping rtio_core reset_phy CSR write
diag: after rtio_mgt startup
diag: before setup_device_map
diag: after setup_device_map
diag: before analyzer start
diag: after analyzer start
diag: before moninj start
diag: after moninj start
diag: before kernel control start
diag: after kernel control start
```

## Populated-Carrier Result From `04_empty_skip_ident_skip_rtio_csrs`

The populated-carrier UART log reached:

```text
INFO(runtime::comms): network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
INFO(runtime::comms): diag: before rtio_mgt startup
INFO(runtime::rtio_mgt): diag: before rtio_mgt setup_sed_spread
INFO(runtime::rtio_mgt): SED spreading disabled by default
INFO(runtime::rtio_mgt): diag: skipping SED spread CSR write value 0
INFO(runtime::rtio_mgt): diag: after rtio_mgt setup_sed_spread
INFO(runtime::rtio_mgt): diag: before rtio_mgt drtio startup
INFO(runtime::rtio_mgt): diag: after rtio_mgt drtio startup
INFO(runtime::rtio_mgt): diag: skipping rtio_core reset_phy CSR write
INFO(runtime::comms): diag: after rtio_mgt startup
INFO(runtime::comms): diag: before setup_device_map
WARN(libboard_artiq): error reading device map (Configuration key `device_map` not found), device names will not be available in RTIO error messages
INFO(runtime::comms): diag: after setup_device_map
INFO(runtime::comms): diag: before analyzer start
INFO(runtime::comms): diag: after analyzer start
INFO(runtime::comms): diag: before moninj start
INFO(runtime::comms): diag: after moninj start
INFO(runtime::comms): diag: before kernel control start
INFO(runtime::comms): diag: after kernel control start
```

The missing `device_map` warning is non-fatal; the runtime continued past it.
There was no further UART output after `after kernel control start`. Inspecting
`comms::main()` shows the next code starts management and control tasks, then
enters the network polling loop, which normally does not print continuously.
This means the 04 result is consistent with an alive but quiet network runtime,
not necessarily a new crash.

## Network-Loop Heartbeat Diagnostic Artifact

The next diagnostic image keeps the same skips as 04 and adds:

- breadcrumbs around `mgmt::start()`
- breadcrumbs around spawning the TCP control accept task
- breadcrumbs when the control accept task starts waiting on TCP port `1381`
- a periodic `diag: network poll heartbeat` while the network event loop runs

Artifact directory:

```text
build/incremental_no_entangler/05_empty_network_loop_heartbeat/
```

Deployable image:

```text
build/incremental_no_entangler/05_empty_network_loop_heartbeat/boot.bin
```

Hashes:

```text
b2aab2c050b59a48d863f1ef6fae5d11b0440525434d72c32e19593a4d04b01f  boot.bin
b6aa84ca6fc5982d34ae139e45ff10f5698ad0b9860f4f3e4f8bbae3794c9e5a  runtime.bin
b9f25f25d12a7cf0174fe6b9e3c12e4f8fbc816ce709188b12554d92769d4545  top.bit
956b952ea1af53b5a356662cf887d2728d515e308ba16cc3a045b27d0d7689be  runtime.elf
87e904f0db263232bc99802d71cb1c59e46fe96b2a878158a603518724b81de8  szl.elf
```

Expected markers:

```text
diag: before mgmt start
diag: after mgmt start
diag: before control accept task spawn
diag: after control accept task spawn
diag: entering network poll loop
diag: control accept task entered
diag: control accept task waiting for connection or idle restart
diag: network poll heartbeat
```

## Populated-Carrier Result From `05_empty_network_loop_heartbeat`

The populated-carrier UART log reached:

```text
INFO(runtime::comms): diag: after kernel control start
INFO(runtime::comms): diag: before mgmt start
INFO(runtime::comms): diag: after mgmt start
INFO(runtime::comms): diag: before control accept task spawn
INFO(runtime::comms): diag: after control accept task spawn
INFO(runtime::comms): diag: entering network poll loop
```

It did not print `diag: control accept task entered` or
`diag: network poll heartbeat`. Since the control accept task is spawned before
`task::block_on()` enters the network poll loop, but it does not run until the
main network loop yields, this result points to the first network poll-loop
iteration before the first async yield.

The next diagnostic instruments that first loop iteration around:

- timer read
- `Sockets::instance().poll(&mut iface, instant)`
- `dev.is_idle()`
- `dev.check_link_change()`
- the first `task::yield().await`

## First Network-Poll Probe Artifact

Artifact directory:

```text
build/incremental_no_entangler/06_empty_network_poll_probe/
```

Deployable image:

```text
build/incremental_no_entangler/06_empty_network_poll_probe/boot.bin
```

Hashes:

```text
dcdb89c4cedfcf338626edb3720d30248c2326ae83b6c33d22fdc41c8a09acbe  boot.bin
7a594994c818de9b1a723efd6f9e8eb53c3117974832459b2f2f5c23299e0e13  runtime.bin
b9f25f25d12a7cf0174fe6b9e3c12e4f8fbc816ce709188b12554d92769d4545  top.bit
9464d2fe3c195aeb005405ec11e2249b0f875fdf7b2646ea82b58e762bf9b5a8  runtime.elf
87e904f0db263232bc99802d71cb1c59e46fe96b2a878158a603518724b81de8  szl.elf
```

Expected markers:

```text
diag: first network loop before timer read
diag: first network loop before sockets poll
diag: first network loop after sockets poll
diag: first network loop before link idle check
diag: first network loop after link idle check
diag: first network loop before link change check
diag: first network loop after link change check
diag: first network loop before yield
diag: control accept task entered
diag: control accept task waiting for connection or idle restart
diag: network poll heartbeat
```

## Populated-Carrier Result From `06_empty_network_poll_probe`

The populated-carrier UART log reached:

```text
INFO(runtime::comms): diag: entering network poll loop
INFO(runtime::comms): diag: first network loop before timer read
INFO(runtime::comms): diag: first network loop before sockets poll
INFO(runtime::comms): diag: first network loop after sockets poll
INFO(runtime::comms): diag: first network loop before link idle check
INFO(runtime::comms): diag: first network loop after link idle check
INFO(runtime::comms): diag: first network loop before link change check
INFO(runtime::comms): diag: first network loop after link change check
INFO(runtime::comms): diag: first network loop before yield
```

It did not print `diag: first network loop after yield`,
`diag: control accept task entered`, or `diag: network poll heartbeat`.

The network poll-loop operations themselves completed through
`dev.check_link_change()`. The stop happens when the async executor reaches the
first `task::yield().await`. In this executor, that yield allows already-spawned
tasks to run before the main network loop resumes. The earlier spawned tasks
include:

- `report_async_rtio_errors()`, which polls `rtio_core::async_error_read()`
- `analyzer::start()`, whose task first calls `arm()` and writes RTIO analyzer
  CSRs

Therefore, the next diagnostic skips those RTIO-facing spawned tasks to test
whether the plain network/control loop can proceed.

## Control-Loop Reachability Artifact

Artifact directory:

```text
build/incremental_no_entangler/07_empty_control_loop_reachability/
```

Deployable image:

```text
build/incremental_no_entangler/07_empty_control_loop_reachability/boot.bin
```

Hashes:

```text
9c244479e31015858f7be58cd60146edc8a9966113d4411dd8e850181a5b4bd5  boot.bin
20a499a9c49410e950a253ee71418ed3778fc852d25034bf9e78e77a16a0ce5f  runtime.bin
b9f25f25d12a7cf0174fe6b9e3c12e4f8fbc816ce709188b12554d92769d4545  top.bit
6e6d04031470d0112ebe7a99f7b83fe95e7ac96d36ca38c0dd388597bc09f15a  runtime.elf
87e904f0db263232bc99802d71cb1c59e46fe96b2a878158a603518724b81de8  szl.elf
```

Expected markers:

```text
diag: skipping async RTIO error reporter task
diag: skipping analyzer start for control-loop reachability test
diag: first network loop before yield
diag: control accept task entered
diag: control accept task waiting for connection or idle restart
diag: first network loop after yield
diag: network poll heartbeat
```

## Populated-Carrier Result From `07_empty_control_loop_reachability`

The populated-carrier UART log reached:

```text
INFO(runtime::comms): diag: skipping async RTIO error reporter task
INFO(runtime::comms): diag: skipping analyzer start for control-loop reachability test
INFO(runtime::comms): diag: entering network poll loop
INFO(runtime::comms): diag: first network loop before timer read
INFO(runtime::comms): diag: first network loop before sockets poll
INFO(runtime::comms): diag: first network loop after sockets poll
INFO(runtime::comms): diag: first network loop before link idle check
INFO(runtime::comms): diag: first network loop after link idle check
INFO(runtime::comms): diag: first network loop before link change check
INFO(runtime::comms): diag: first network loop after link change check
INFO(runtime::comms): diag: first network loop before yield
INFO(runtime::comms): diag: control accept task entered
INFO(runtime::comms): diag: control accept task waiting for connection or idle restart
INFO(runtime::comms): diag: first network loop after yield
INFO(runtime::comms): no idle kernel found
INFO(runtime::comms): diag: network poll heartbeat
INFO(libboard_zynq::eth): eth: got Link { speed: S1000, duplex: Full }
INFO(runtime::comms): diag: network poll heartbeat
INFO(runtime::comms): diag: network poll heartbeat
```

This confirms that the plain network/control path is alive on the populated
carrier when the known failing RTIO CSR operations and early RTIO-facing
background tasks are skipped. The board reaches the first async yield, schedules
the control accept task, reports no idle kernel, detects a 1 Gbit full-duplex
Ethernet link, and continues printing network poll heartbeats.

The result also narrows the 06 stop: the first async yield itself was not the
fundamental blocker. Rather, after that yield, one of the previously spawned
RTIO-facing tasks was blocking before the control task could run. The skipped
tasks in 07 were:

- `report_async_rtio_errors()`, which polls `rtio_core::async_error_read()`
- `analyzer::start()`, whose first task action arms RTIO analyzer CSRs

## Current Finding After Test 21

The `21_dio0_dio1_ps_fclk_axi_local_write_sink_probe` populated-carrier test is
the decisive positive comparison to test `20`.

Artifact:

```text
build/incremental_no_entangler/21_dio0_dio1_ps_fclk_axi_local_write_sink_probe/boot.bin
sha256 9e111f71b97c3b34d74f3ed13b9280a691b343ea77df60c5be204ba9bfd82212
```

Experiment `21` kept Entangler absent, kept only DIO EEM0 and DIO EEM1, used
hardware revision `v1.0`, removed standalone `SYS_CRG`, and clocked the active
generated PL `sys` fabric from Zynq PS FCLK. It also avoided the bootstrap
AXI2CSR rename from experiments `18`-`20`.

The generated CSR map included:

```text
identifier                  = 0x80000000
rtio_core                   = 0x80000800
ps_fclk_write_sink::value   = 0x80001000
rtio                        = 0x80001800
rtio_dma                    = 0x80002000
rtio_moninj                 = 0x80003000
sys_crg                     = absent
bootstrap_write_sink        = absent
```

The user-provided UART log reached the decisive write and printed the
after-write marker:

```text
diag: experiment 21 PS-FCLK local write sink probe: no post-network PL CSR reads have been attempted before the decisive local write
diag: before experiment 21 PS-FCLK local write sink CSR write value 0 address=0x80001000
diag: after experiment 21 PS-FCLK local write sink CSR write value 0
```

The runtime then continued through RTIO-management exit, device-map setup,
moninj startup, kernel-control startup, management startup, control accept task
startup, the network poll loop, Ethernet link-up, and repeated heartbeats:

```text
diag: after rtio_mgt setup_sed_spread
diag: skipping rtio_core reset_phy CSR write
diag: after rtio_mgt startup
diag: after mgmt start
diag: after control accept task spawn
diag: entering network poll loop
eth: got Link { speed: S1000, duplex: Full }
diag: network poll heartbeat
```

Interpretation:

- The dummy generated CSR write succeeds under PS-FCLK sys using the normal
  AXI2CSR/CSR path.
- The experiment `20` failure is not a universal PS GP AXI to AXI2CSR write
  completion failure.
- The remaining suspect set is now the standalone `SYS_CRG`/MMCM/reset
  integration, bootstrap clock-domain interactions, or the bootstrap AXI2CSR
  diagnostic wiring used in experiments `18`-`20`.
- This is still not a production RTIO image: `identifier_read()`, firmware
  SYS/RTIO clock switching, async RTIO error reporting, analyzer startup, RTIO
  PHY reset, Entangler logic, and extra EEM cards are intentionally skipped.

Next diagnostic direction: keep the dummy local write-sink test and vary only
one clock/bridge integration detail at a time. The most useful follow-up is a
minimal standalone-`SYS_CRG` image with a normal, non-bootstrap-renamed AXI2CSR
path and the same single dummy write discipline.
