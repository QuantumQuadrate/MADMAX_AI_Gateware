# Boot Log: 16 DIO0/DIO1 Bootstrap SED Spread Probe

Date: 2026-05-27

Artifact to boot:

```text
build/incremental_no_entangler/16_dio0_dio1_bootstrap_sed_spread_probe/boot.bin
```

Source JSON:

```text
build/generated/experiment_16_dio0_dio1_bootstrap_sed_spread_probe.json
```

## Build Result

Packaged artifact:

```text
build/incremental_no_entangler/16_dio0_dio1_bootstrap_sed_spread_probe/boot.bin
sha256 316982973d17eb87d0cd9aedfb373eabf2e6a317967f169b8ad9af5894e8ca61
```

Supporting outputs:

```text
top.bit     sha256 5ca82db5aa2613e474d8467e265e9c4a9cbfe66f4617932c9d12977b7071318d
runtime.elf sha256 b3383bf51a495fa91a644a0969261703c3beac42e417c1f0c90baac46f560526
runtime.bin sha256 c50e409f21668680cf4483d95e10a00b7ab6e6541efab566cd801e54552e5508
source JSON sha256 39016ff8b18764ce8d7565926a62eda73c7c609b9a42c050fff6b948d0e4854e
```

Vivado completed route and bitstream generation successfully. The final timing
report shows WNS `0.448 ns`, TNS `0.000 ns`, and `All user specified timing
constraints are met.` The route-status report shows `0` nets with routing
errors.

## Hardware Constraints

This artifact is for the real Node Kasli-SoC carrier hardware revision `v1.0`,
not the unpopulated v1.1 test Kasli. The parsed source JSON contains:

```text
hw_rev: v1.0
peripherals: DIO EEM0, DIO EEM1
Entangler: absent
extra EEM cards: absent
```

The archived generated Verilog also keeps standalone SYS_CRG on the bootstrap
clock path by default:

```text
reg sys_crg_storage_full = 1'd0;
```

## Diagnostic Purpose

Experiment `16` keeps the narrow two-DIO no-Entangler shape from experiments
`13` through `15`. It keeps the bootstrap-SYS identifier probe from `15`, then
attempts the SED-spread CSR write again while SYS_CRG remains on the bootstrap
clock path.

This is meant to separate a general RTIO-core CSR write problem from a problem
that appears only after switching the standalone SYS_CRG/MMCM path away from
bootstrap.

Still skipped in this image:

- SYS/RTIO clock-switch firmware write
- RTIO PHY reset CSR write
- analyzer startup
- async RTIO error reporter task
- Entangler logic
- additional EEM cards beyond DIO0 and DIO1

Expected decisive UART markers:

```text
diag: before bootstrap-SYS identifier_read CSR probe
diag: bootstrap-SYS identifier_read returned 9+unknown;16_dio0_dio1_bootstrap_sed_spread_probe
diag: after bootstrap-SYS identifier_read CSR probe
diag: before rtio_mgt startup
SED spreading disabled by default
diag: before bootstrap-SYS SED spread CSR write value 0 address=0x80001008
diag: after bootstrap-SYS SED spread CSR write value 0
diag: after rtio_mgt setup_sed_spread
diag: skipping rtio_core reset_phy CSR write
diag: after rtio_mgt startup
diag: after control accept task spawn
diag: first network loop heartbeat
```

If the populated-carrier boot reaches the `after bootstrap-SYS SED spread CSR
write` marker, the SED-spread CSR write can complete while SYS_CRG remains on
the bootstrap path. That would push suspicion back toward the clock switch to
the cleaned fabric clock or the post-switch SYS/RTIO clock path.

If it stops after:

```text
diag: before bootstrap-SYS SED spread CSR write value 0 address=0x80001008
```

then the SED-spread CSR write itself remains a blocker even with SYS_CRG held
on bootstrap.

## Archive Contents

Artifact directory:

```text
build/incremental_no_entangler/16_dio0_dio1_bootstrap_sed_spread_probe/
```

Archived together:

```text
source.json
boot.bin
top.bit
runtime.elf
runtime.bin
pl.rs
rustc-cfg
mem.rs
top_timing.rpt
top_route_status.rpt
top_drc.rpt
build-manifest.txt
archive-sha256sums.txt
```

## Observed Boot Result

The user-provided populated-carrier boot log reaches:

```text
[     2.633516s]  INFO(runtime::comms): network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
[     2.652920s]  INFO(runtime::comms): diag: skipping async RTIO error reporter task
[     2.654756s]  INFO(runtime::comms): diag: before bootstrap-SYS identifier_read CSR probe
```

No `bootstrap-SYS identifier_read returned`, `after bootstrap-SYS
identifier_read`, or SED-spread markers were observed.

This means experiment `16` did not actually test the SED-spread CSR write. It
reproduced the same post-network PL CSR hang point as the standalone-SYS
identifier probes: the runtime can initialize RAM, GIC, I2C, both I/O
expanders, Si5324, Ethernet, and network addressing, then blocks on the explicit
post-network `identifier_read()` transaction.

The result narrows the next experiment: skip `identifier_read()` again and test
the RTIO-core SED-spread CSR write under the same bootstrap-SYS conditions, or
move the next probe lower than `identifier_read()` by using a different,
non-blocking/metadata-only marker before any PL CSR transaction.
