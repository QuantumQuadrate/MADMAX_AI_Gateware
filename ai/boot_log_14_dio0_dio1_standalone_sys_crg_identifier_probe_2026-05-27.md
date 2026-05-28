# Boot Log: 14 DIO0/DIO1 Standalone SYS_CRG Identifier Probe

Date: 2026-05-27

Artifact to boot:

```text
build/incremental_no_entangler/14_dio0_dio1_standalone_sys_crg_identifier_probe/boot.bin
```

Source JSON:

```text
build/generated/experiment_14_dio0_dio1_standalone_sys_crg_identifier_probe.json
```

## Build Result

Packaged artifact:

```text
build/incremental_no_entangler/14_dio0_dio1_standalone_sys_crg_identifier_probe/boot.bin
sha256 ef485c0f679c83fa12a3109e9a1a2b9ca50101ce13ad09bc3308bda4a4f59730
```

Supporting outputs:

```text
top.bit     sha256 d32020ad592d7a699f3c57e843971af2b81eabab93c7ad9a81fb4d51fe874f5c
runtime.elf sha256 5ffe7ab6d6139a50c6288476df58216755b3a40cf4845868b9fecc08f154811f
runtime.bin sha256 151aced5146ccf6b2810bdb689687ded0a3f9c3ea3b4e46d9384df929efcd7e4
pl.rs       sha256 c569db1bc14763b25ae008520b11a4d429f42a9714281c7eb323fb9223ef13a7
rustc-cfg   sha256 eaca1744efa148a9172e8c1577fbe7d1e6bfc334fd53e184d45fd6ac89fb8591
mem.rs      sha256 95c24a456947f79c8f531b00e60313f75131b850a630c12650b5bfae32ab9265
source JSON sha256 e1c91e50c829fe8eea294157839f6870bd3ed104c35618b0751ccecffeaa7ebf
```

Vivado completed route and bitstream generation successfully. The final timing
report shows WNS `0.278 ns`, TNS `0.000 ns`, and `All user specified timing
constraints are met.` The route-status report shows `0` nets with routing
errors.

## Diagnostic Purpose

Experiment `14` is the next narrow step after successful experiment `13`.

What changed relative to `13`:

- keep the same two-DIO source shape: DIO on EEM0 and EEM1 only,
- keep Entangler absent,
- restore the standalone `GenericStandalone` SYS clocking path:
  `ps_cd_sys=False`, `cdr_clk_clean_fabric`, `GTPBootstrapClock`,
  `zynq_clocking.SYSCRG`, the generated `sys_crg` CSR block, and SI5324/SMA
  clock configuration,
- keep the `SYSCRG.clock_switch` CSR reset default at `1` so the diagnostic
  can use the standalone SYS path without performing a firmware
  `clock_switch_write(1)`,
- keep early `identifier_read()` skipped during initial runtime startup,
- keep firmware SYS/RTIO clock switching skipped,
- keep SED spread, RTIO PHY reset, analyzer startup, and async RTIO error
  reporting skipped,
- remove the experiment `11`/`12` SYS_CRG `current_clock_read()` probe from the
  post-network path,
- perform one explicit `identifier_read()` CSR probe after networking setup.

This image asks whether the basic identifier CSR transaction still completes
when the PL `sys` domain is again produced by the standalone SYS_CRG/MMCM path.
It intentionally does not touch SYS_CRG status CSRs or RTIO-core write CSRs.

Expected decisive markers:

```text
diag: before standalone-SYS identifier_read CSR probe
diag: standalone-SYS identifier_read returned 9+unknown;14_dio0_dio1_standalone_sys_crg_identifier_probe
diag: after standalone-SYS identifier_read CSR probe
diag: before rtio_mgt startup
```

Expected supporting RTIO preflight markers if the identifier probe returns:

```text
diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=0x... rtio_core=0x...
diag: rtio csr preflight: runtime cfg has_sys_crg=true
diag: clock preflight: generated config has_si5324=true
diag: clock preflight: SYS/RTIO clock switch remains skipped in this diagnostic image
```

## Interpretation Guide

If the populated-carrier boot reaches the `standalone-SYS identifier_read
returned` and `after` markers, then the basic AXI-to-CSR path and identifier CSR
also work with the standalone SYS_CRG/MMCM-driven `sys` domain. That would push
the failure toward the specific SYS_CRG status CSR and RTIO-core CSR accesses
seen in experiments `09`, `11`, and `12`, rather than the standalone `sys`
clock domain as a whole.

If it stops after:

```text
diag: before standalone-SYS identifier_read CSR probe
```

then experiment `13` versus `14` becomes a very clean split: PS-FCLK-driven
`sys` allows identifier CSR completion, while standalone SYS_CRG/MMCM-driven
`sys` does not. That would strongly implicate the restored standalone
clock/reset fabric itself.

If it stops before `network addresses`, then the restored standalone SYS_CRG
path changed an earlier boot stage than the explicit CSR probe. In that case,
compare the last marker against experiment `13` before adding any more EEM cards
or reintroducing the Entangler core.

## Observed Boot Result

The user-provided populated-carrier UART log shows this image reaching the
decisive standalone-SYS identifier probe, but not returning from it.

The boot successfully completed all early stages:

```text
[     0.014361s]  INFO(szl): Simple Zynq Loader starting...
[     0.107506s]  INFO(szl): Loading gateware
[     0.425668s]  INFO(szl): Loading runtime
[     0.000067s]  INFO(runtime): NAR3/Zynq7000 starting...
```

Runtime initialization reached the expected board and clock setup markers:

```text
[     0.037519s]  INFO(libboard_zynq::i2c): PCA9548 detected
[     0.184092s]  INFO(runtime): diag: after io expander init 1
[     0.245866s]  INFO(runtime): diag: before rtio_clocking init
[     0.253108s]  INFO(runtime::rtio_clocking): using 125MHz reference to make 125MHz RTIO clock with PLL
[     0.624538s]  INFO(libboard_artiq::si5324): waiting for Si5324 lock...
[     2.581871s]  INFO(libboard_artiq::si5324):   ...locked
[     2.581883s]  INFO(runtime::rtio_clocking): diag: skipping SYS/RTIO clock switch for populated-carrier test
[     2.591167s]  INFO(runtime): diag: after rtio_clocking init
```

Ethernet also reached address assignment:

```text
[     2.633190s]  INFO(runtime::comms): network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
```

The last observed diagnostic marker is:

```text
[     2.654756s]  INFO(runtime::comms): diag: before standalone-SYS identifier_read CSR probe
```

No matching markers were observed:

```text
diag: standalone-SYS identifier_read returned 9+unknown;14_dio0_dio1_standalone_sys_crg_identifier_probe
diag: after standalone-SYS identifier_read CSR probe
diag: before rtio_mgt startup
```

## Updated Interpretation

Experiment `14` confirms the clean split that experiment `13` set up:

- with PL `sys` clocked directly from Zynq PS FCLK and standalone `sys_crg`
  absent, `identifier_read()` returns successfully in experiment `13`,
- with standalone SYS_CRG/MMCM-driven `sys` restored, the same post-network
  `identifier_read()` does not return in experiment `14`.

This means the populated-carrier failure is not a pre-network bring-up problem
introduced by restoring standalone clocking. The board still loads gateware,
enters runtime, initializes I2C and both I/O expanders, locks the Si5324,
skips the firmware SYS/RTIO clock switch, and prints network addresses.

The stronger suspect is now the standalone SYS_CRG/MMCM-driven `sys`
clock/reset/CSR response path itself, or the AXI-to-CSR transaction crossing
into that restored `sys` fabric. The failure is broader than the particular
SYS_CRG status CSR and RTIO-core CSR addresses tested in experiments `09`,
`11`, and `12`, because experiment `14` hangs on the identifier CSR while using
the restored standalone `sys` domain.
