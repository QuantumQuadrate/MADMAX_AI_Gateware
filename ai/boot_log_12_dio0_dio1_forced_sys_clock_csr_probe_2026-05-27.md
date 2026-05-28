# Boot Log: 12 DIO0/DIO1 Forced-SYS SYS_CRG Read Probe

Date: 2026-05-27

Artifact to boot:

```text
build/incremental_no_entangler/12_dio0_dio1_forced_sys_clock_csr_probe/boot.bin
```

Source JSON:

```text
build/generated/incremental_no_entangler_02_dio0_dio1.json
```

## Build Result

The test `12` BOOT image was built from the same 2-DIO JSON used for tests
`08` through `11`.

Packaged artifact:

```text
build/incremental_no_entangler/12_dio0_dio1_forced_sys_clock_csr_probe/boot.bin
sha256 30550f50ee757705f5cd2ec69d188f0c1402ffebea50bbbd17693eedd12b5ebf
```

Supporting outputs:

```text
top.bit     sha256 7c90856e236eb9a5dd28f8eecb85065d2bdf999a4a3a983b1dcf5c22cfa36574
runtime.elf sha256 64bc0e84a67e96e5a763d5ee8232532ce45fc5e2b96585b04a8fe21b713c3d13
runtime.bin sha256 d5a27aa99b29746dd9648bb5b14968baab58d563c9628c89417d18517a1faf31
source JSON sha256 f935b5a83a5e1c3d0baa027062278e319963e3525188d49a93a8c6ebc8026921
```

Vivado completed route and bitstream generation successfully. The final timing
report shows WNS `0.282 ns` and `All user specified timing constraints are
met.` The route-status report shows `0` nets with routing errors. The DRC report
contains warning-only results: 8 `BUFC-1`, 1 `LVDS-1`, and 1 `RTSTAT-10`.

## Runtime And Gateware Delta From Test 11

Test `12` keeps the successful test `10`/`11` firmware path intact:

- `identifier_read()` remains skipped.
- Firmware SYS/RTIO clock switching remains skipped.
- `sed_spread_enable_write(0)` remains skipped.
- `reset_phy_write(1)` remains skipped.
- The analyzer remains skipped.
- The async RTIO error reporter remains skipped.

The one new variable is gateware-side SYS_CRG clock selection. In
`src/gateware/zynq_clocking.py`, the standalone SYS_CRG `clock_switch`
`CSRStorage` now resets to `1`, so the clock-switch FSM defaults toward the
post-Si5324/main SYS clock path without a firmware
`sys_crg::clock_switch_write(1)` transaction. The generated Verilog confirms:

```text
reg sys_crg_storage_full = 1'd1;
```

The read-only SYS_CRG probe remains after network setup and immediately before
RTIO management startup.

Expected decisive markers:

```text
diag: before forced-SYS SYS_CRG current_clock_read probe
diag: forced-SYS SYS_CRG current_clock_read returned <value>
diag: after forced-SYS SYS_CRG current_clock_read probe
diag: before rtio_mgt startup
```

## Observed Boot Result

The user-provided populated-carrier UART log shows test `12` reaching the same
successful path as test `11` through:

- SZL gateware/runtime loading,
- runtime RAM and GIC initialization,
- skipped `identifier_read()`,
- I2C and both Kasli I/O expander initialization/service,
- Si5324 lock,
- skipped firmware SYS/RTIO clock switch,
- network address assignment at IPv4 `192.168.1.75`,
- and skipped async RTIO error reporter startup.

It then prints:

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

The immediate stop is still inside, or at least during, this read-only CSR
transaction:

```rust
pl::csr::sys_crg::current_clock_read()
```

## Interpretation

The read still hangs, so the issue is not just the skipped firmware SYS/RTIO
clock switch. PS-to-PL CSR access is still unresponsive even with the SYS clock
selection forced/defaulted in gateware.

This result argues against advancing to RTIO-core write probes yet. The next
diagnostic branch should stay focused on why actual PL CSR transactions can
hang after otherwise successful runtime/network bring-up, even when the SYS_CRG
clock source is forced from gateware instead of selected by firmware.
