# Boot Log: 15 DIO0/DIO1 SYS_CRG Bootstrap Identifier Probe

Date: 2026-05-27

Artifact to boot:

```text
build/incremental_no_entangler/15_dio0_dio1_sys_crg_bootstrap_identifier_probe/boot.bin
```

Source JSON:

```text
build/generated/experiment_15_dio0_dio1_sys_crg_bootstrap_identifier_probe.json
```

## Build Result

Packaged artifact:

```text
build/incremental_no_entangler/15_dio0_dio1_sys_crg_bootstrap_identifier_probe/boot.bin
sha256 cdf2921caddeb2d787faf34aba4767b9131c2e4e7232889931883c1fe0097a33
```

Supporting outputs:

```text
top.bit     sha256 2cb5da7a645e76115d9e61be0439e4d8801578a85a4da355b745eb8a9d31567a
runtime.elf sha256 5f6f86db203e3cc2d28100ec35207c889741a6d8c67bf339c945d927f7b9ccd9
runtime.bin sha256 7621d10ee61ec207aff8255a1a1cdfb0c4ab1f77bb3ed1c78201808ed060a049
pl.rs       sha256 c569db1bc14763b25ae008520b11a4d429f42a9714281c7eb323fb9223ef13a7
rustc-cfg   sha256 eaca1744efa148a9172e8c1577fbe7d1e6bfc334fd53e184d45fd6ac89fb8591
mem.rs      sha256 95c24a456947f79c8f531b00e60313f75131b850a630c12650b5bfae32ab9265
source JSON sha256 5b1344b54233aa6b24df2861cf375b2a88035b68c9dfd7d614c6d28d91cb944c
```

Vivado completed route and bitstream generation successfully. The final timing
report shows WNS `0.340 ns`, TNS `0.000 ns`, and `All user specified timing
constraints are met.` The route-status report shows `0` nets with routing
errors.

## Diagnostic Purpose

Experiment `15` is the narrow clock-selection A/B test after failed experiment
`14`.

What changed relative to `14`:

- keep the same two-DIO source shape: DIO on EEM0 and EEM1 only,
- keep Entangler absent,
- keep standalone `GenericStandalone` SYS_CRG present, including
  `cdr_clk_clean_fabric`, `GTPBootstrapClock`, `zynq_clocking.SYSCRG`, and the
  generated `sys_crg` CSR block,
- change the standalone SYS_CRG `clock_switch` CSR reset/default back to `0`,
  so the clock-switch FSM remains on the bootstrap/MMCM `CLKIN2` path unless
  firmware explicitly writes the switch CSR,
- keep firmware SYS/RTIO clock switching skipped, so no runtime
  `clock_switch_write(1)` is performed,
- keep early `identifier_read()` skipped during initial runtime startup,
- keep SED spread, RTIO PHY reset, analyzer startup, and async RTIO error
  reporting skipped,
- perform one explicit `identifier_read()` CSR probe after networking setup.

The generated Verilog confirms this clock-selection split:

```text
reg sys_crg_storage_full = 1'd0;
```

Expected decisive markers:

```text
diag: before bootstrap-SYS identifier_read CSR probe
diag: bootstrap-SYS identifier_read returned 9+unknown;15_dio0_dio1_sys_crg_bootstrap_identifier_probe
diag: after bootstrap-SYS identifier_read CSR probe
diag: before rtio_mgt startup
```

## Interpretation Guide

If the populated-carrier boot reaches the `bootstrap-SYS identifier_read
returned` and `after` markers, then SYS_CRG can exist and the AXI/CSR bridge can
cross into the generated `sys` domain as long as SYS_CRG stays on the bootstrap
clock path. That would implicate the switch to `cdr_clk_clean_fabric`, the
Si5324-cleaned clock, or the MMCM main-input path.

If it stops after:

```text
diag: before bootstrap-SYS identifier_read CSR probe
```

then merely keeping standalone SYS_CRG present is still enough to break the
post-network PL CSR transaction. That would push suspicion toward SYS_CRG
presence/reset behavior itself, or toward the CSR/AXI bridge crossing into the
generated `sys` domain even before switching to the cleaned-clock path.

No EEM cards or Entangler logic were added for this experiment.

## Observed Boot Result

Hardware boot result is pending. This note records the build artifact and the
expected UART markers for the populated-carrier run.
