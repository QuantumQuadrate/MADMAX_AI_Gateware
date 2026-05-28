# Boot Log: 21 DIO0/DIO1 PS-FCLK AXI Local Write Sink Probe

Date: 2026-05-27

Artifact booted:

```text
build/incremental_no_entangler/21_dio0_dio1_ps_fclk_axi_local_write_sink_probe/boot.bin
```

Source JSON:

```text
build/incremental_no_entangler/21_dio0_dio1_ps_fclk_axi_local_write_sink_probe/source.json
```

## Build Result

Packaged artifact:

```text
build/incremental_no_entangler/21_dio0_dio1_ps_fclk_axi_local_write_sink_probe/boot.bin
sha256 9e111f71b97c3b34d74f3ed13b9280a691b343ea77df60c5be204ba9bfd82212
```

Supporting outputs:

```text
top.bit     sha256 8530fe5e5d5306aca5118cee36f1281c43c62b3f150da47e8329145faf31f801
runtime.elf sha256 6fe2f9728385b74ed5ae7c30895bae0ca377ba0a7eceb4126cd7ed0222e2c5af
runtime.bin sha256 fd200f33f0b8f4b6b5e76bb3fa8c6b11a7a5820f39b9880244aed2b9a91320c8
source JSON sha256 9c6fa1512ed8f04beca4f1d5507165eecb521b8067712c8b07b882949a9135cf
```

Vivado completed route and bitstream generation successfully. The final timing
report shows WNS `1.907 ns`, TNS `0.000 ns`, and `All user specified timing
constraints are met.` The route-status report shows `0` nets with routing
errors.

Timing caveat: this is a PS-FCLK diagnostic image with standalone `SYS_CRG`
removed. Vivado reports `no_clock` and unconstrained endpoint checks for
`PS7/FCLKCLK[0]`; this image is useful for CSR-path isolation, not production
RTIO timing signoff.

## Hardware Constraints

This artifact is for the real populated Node Kasli-SoC carrier hardware
revision `v1.0`. The parsed source JSON contains:

```text
hw_rev: v1.0
peripherals: DIO EEM0, DIO EEM1
Entangler: absent
extra EEM cards: absent
```

The generated Rust configuration contains:

```text
has_ps_fclk_write_sink
has_rtio_core
ps_fclk_local_write_sink_probe
ps_fclk_sys_probe
hw_rev="v1.0"
rtio_frequency="125.0"
```

`has_sys_crg`, `has_si5324`, `bootstrap_axi_csr_timeout_probe`, and
`bootstrap_axi_local_write_sink_probe` are absent from the generated
`rustc-cfg`.

## Diagnostic Purpose

Experiment `21` tests whether a dummy generated CSR write completes when the
active PL `sys` fabric is clocked directly from Zynq PS FCLK, matching the
experiment `13` clocking strategy, instead of using standalone `SYS_CRG`,
MMCM/bootstrap clocking, or the bootstrap-renamed AXI2CSR path from experiments
`18`-`20`.

The first intentional post-network PL CSR transaction is exactly one write:

```text
csr::ps_fclk_write_sink::value_write(0)
```

Still skipped in this image:

- all `identifier_read()` calls
- SYS/RTIO clock-switch firmware write
- async RTIO error reporter task
- analyzer startup
- RTIO PHY reset CSR write
- Entangler logic
- additional EEM cards beyond DIO0 and DIO1
- bootstrap AXI2CSR diagnostic renaming

## Generated CSR Addresses

```text
identifier                  = 0x80000000
rtio_core                   = 0x80000800
ps_fclk_write_sink::value   = 0x80001000
rtio                        = 0x80001800
rtio_dma                    = 0x80002000
cri_con                     = 0x80002800
rtio_moninj                 = 0x80003000
rtio_analyzer               = 0x80003800
sys_crg                     = absent
bootstrap_write_sink        = absent
```

## Expected UART Markers

```text
diag: experiment 21 PS-FCLK local write sink probe: no post-network PL CSR reads have been attempted before the decisive local write
diag: before experiment 21 PS-FCLK local write sink CSR write value 0 address=0x80001000
diag: after experiment 21 PS-FCLK local write sink CSR write value 0
diag: after rtio_mgt setup_sed_spread
diag: entering network poll loop
```

## Observed Boot Result

The user-provided populated-carrier boot log shows SZL loading gateware and
runtime, then runtime initializing RAM, GIC, I2C, both I/O expanders, log setup,
networking, RTIO metadata preflight, management/control services, and Ethernet
link-up.

Key preflight markers:

```text
network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=absent rtio_core=0x80000800
diag: rtio csr preflight: ps_fclk_write_sink base=0x80001000 value=0x80001000
diag: rtio csr preflight: runtime cfg has_sys_crg=false
```

Decisive result:

```text
diag: experiment 21 PS-FCLK local write sink probe: no post-network PL CSR reads have been attempted before the decisive local write
diag: before experiment 21 PS-FCLK local write sink CSR write value 0 address=0x80001000
diag: after experiment 21 PS-FCLK local write sink CSR write value 0
```

The boot then continued past RTIO management and into the long-running network
loop:

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

## Finding

Experiment `21` passes. The first intentional post-network PL CSR transaction,
a write to the dummy `ps_fclk_write_sink` CSRStorage at `0x80001000`, completes
from the ARM/PS point of view and prints the after-write marker.

This proves the generated CSR write path is functional when the PL `sys` fabric
is driven from Zynq PS FCLK and the normal AXI2CSR/CSR path is used. Therefore
the experiment `20` hang is not a fundamental failure of:

- PS GP AXI to AXI2CSR write completion in all configurations
- generated CSRStorage write acknowledgement in all configurations
- the populated carrier, SD boot path, runtime entry, I2C, I/O expanders, or
  Ethernet/network loop

The remaining suspect set shifts back toward integration that is absent from
experiment `21` but present in the failing standalone/bootstrap variants:

- standalone `SYS_CRG` / MMCM / reset integration
- bootstrap clock-domain interactions
- the diagnostic bootstrap AXI2CSR renaming used by experiments `18`-`20`
- CSR transactions that depend on the standalone SYS/RTIO clock-domain
  arrangement

This image still does not validate normal RTIO operation because SED spread,
RTIO PHY reset, analyzer startup, async RTIO error reporting, and the
Entangler are intentionally skipped.

## Classification

Observed classification: case `1`.

The after-write marker printed, so the generic generated CSR write path works
under PS-FCLK sys. The failure is likely introduced by standalone
`SYS_CRG`/MMCM/bootstrap clock-domain integration or by the bootstrap AXI2CSR
diagnostic wiring.

## Next Diagnostic Direction

Do not treat experiment `20` as proof that all generated CSR writes are broken.
Experiment `21` disproves that broader interpretation.

The next useful branch should compare PS-FCLK normal AXI2CSR against standalone
SYS_CRG in the smallest possible increment. Keep the dummy write-sink target and
single-write discipline, then vary only one of:

- add standalone `SYS_CRG` without bootstrap AXI2CSR renaming,
- add bootstrap clocking without moving AXI2CSR into the bootstrap domain,
- add a timeout/observer around the AXI2CSR response path,
- only after the dummy write path is understood, reattempt an RTIO-core
  SED-spread write.

## Prompt For Experiment 22

```text
Continue the Kasli-SoC real Node v1.0 diagnostic ladder from experiment 21.

Current finding:
- Experiment 21 booted on the real populated Node v1.0 Kasli.
- It skipped identifier_read(), Entangler, firmware SYS/RTIO clock switching, async RTIO error reporter, analyzer startup, and RTIO PHY reset CSR write.
- It kept only DIO EEM0 and DIO EEM1.
- It removed standalone SYS_CRG and clocked the active generated PL sys fabric directly from Zynq PS FCLK.
- It used the normal AXI2CSR/CSR path, not the bootstrap-renamed AXI2CSR path from experiments 18-20.
- It performed no post-network PL CSR reads before the decisive write.
- It reached:
  diag: before experiment 21 PS-FCLK local write sink CSR write value 0 address=0x80001000
  diag: after experiment 21 PS-FCLK local write sink CSR write value 0
- It then continued through RTIO-management exit, moninj, kernel-control, management, control accept task startup, network poll loop, 1 Gbit Ethernet link-up, and repeated heartbeats.
- Conclusion: a dummy generated CSRStorage write completes from ARM/PS when sys is PS-FCLK-driven and AXI2CSR is normal. Experiment 20 is not proof that all generated CSR writes are broken; the remaining suspect is the standalone SYS_CRG/MMCM/reset integration, bootstrap clock-domain interactions, or the bootstrap AXI2CSR diagnostic wiring.

Design experiment 22.

Variant name:
22_dio0_dio1_standalone_sys_crg_normal_axi_local_write_sink_probe

Goal:
Restore standalone SYS_CRG/MMCM-driven sys while keeping the normal, non-bootstrap-renamed AXI2CSR/CSR path. Re-run the same dummy local write-sink discipline from experiment 21. This isolates whether restoring standalone SYS_CRG alone is enough to break a generated CSRStorage write.

Requirements:
- Target the real Node v1.0 Kasli; every generated JSON must use `"hw_rev": "v1.0"`.
- Keep Entangler absent.
- Keep only DIO EEM0 and DIO EEM1.
- Build and archive `boot.bin`, not only `top.bit`.
- Restore standalone SYS_CRG/MMCM-driven sys, as in the standalone-clock variants.
- Do not apply the experiment 18-20 bootstrap AXI2CSR clock-domain rename.
- Keep firmware SYS/RTIO clock-switch write skipped.
- Keep all `identifier_read()` calls skipped.
- Keep async RTIO error reporter skipped.
- Keep analyzer startup skipped.
- Keep RTIO PHY reset CSR write skipped.
- Keep all RTIO-core writes skipped until after the dummy local write result is known.

Implementation direction:
- Add a new variant constant for `22_dio0_dio1_standalone_sys_crg_normal_axi_local_write_sink_probe`.
- Add a minimal local CSR write sink, for example `standalone_sys_write_sink`, as a `CSRStorage(32)` in the normal generated CSR path.
- The sink should live in the normal sys-domain CSR fabric used by standalone SYS_CRG, not in the bootstrap domain and not in the PS-FCLK-only experiment path.
- Do not rename AXI2CSR into `bootstrap`.
- Do not read `standalone_sys_write_sink`, `sys_crg`, `identifier`, `rtio_core`, `rtio`, `rtio_dma`, `rtio_moninj`, `bootstrap_write_sink`, `ps_fclk_write_sink`, or any other PL CSR before the decisive local write.
- Print a UART marker immediately before the local write, including the generated sink address.
- Perform exactly one direct write to the standalone-sys local CSR sink.
- Print a UART marker immediately after the local write.
- Only after the after-local-write marker prints may the firmware attempt a secondary comparison write, and the first secondary comparison should be `csr::rtio_core::sed_spread_enable_write(0)` with clear before/after UART markers.
- Do not perform optional CSR reads at all in this experiment unless they occur after all write markers and are clearly marked disposable.

Expected classification:
1. Stops after the before-local-write marker: restoring standalone SYS_CRG/MMCM-driven sys is enough to break even a dummy generated CSRStorage write on the normal AXI2CSR path.
2. Prints the after-local-write marker, then stops on the secondary RTIO-core SED write: standalone SYS_CRG can complete local generated CSR writes, but the failure is specific to RTIO-core/sys-domain target logic or its reset/clocking.
3. Prints both after-write markers: standalone SYS_CRG plus normal AXI2CSR is not sufficient to reproduce the hang; compare against experiments 18-20 for bootstrap AXI2CSR rename and CSR ordering effects.
4. Any optional post-write CSR read hang is secondary and must not change the decisive classification.

Before building, explicitly verify:
1. Source JSON contains `"hw_rev": "v1.0"`.
2. Artifact is intended for the real Node v1.0 Kasli.
3. No Entangler or extra EEM cards were added.
4. Standalone SYS_CRG is present and `has_sys_crg=true` appears in generated runtime cfg.
5. The bootstrap AXI2CSR rename feature is absent.
6. There is no post-network `identifier_read()`.
7. There are no post-network CSR reads before the decisive local write.
8. Generated `rustc-cfg` exposes the experiment-22 write-sink feature and generated `pl.rs` contains the local sink address.

After building, archive source JSON, boot.bin, top.bit, runtime.elf/bin, pl.rs, rustc-cfg, mem.rs, timing report, route-status report, and manifest together. Report boot.bin path and SHA256 first, then WNS/TNS, route error count, generated SYS_CRG presence, generated sink address, generated RTIO-core SED address, and expected UART markers.
```
