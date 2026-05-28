# Boot Log: 11 DIO0/DIO1 SYS_CRG Read Probe

Date: 2026-05-27

Artifact to boot:

```text
build/incremental_no_entangler/11_dio0_dio1_sys_crg_read_probe/boot.bin
```

Source JSON:

```text
build/generated/incremental_no_entangler_02_dio0_dio1.json
```

## Build Result

The test `11` BOOT image was built from the same 2-DIO JSON used for test `10`.

Packaged artifact:

```text
build/incremental_no_entangler/11_dio0_dio1_sys_crg_read_probe/boot.bin
sha256 f72674ce07da0952740a0e4f04cab4757185f6d3104bd150212b7383509f3764
```

Supporting outputs:

```text
top.bit     sha256 d47010f63a1097bba4c578135ad56b69527be0a88e91928767adc0f8ee838a72
runtime.elf sha256 c845db4e9a4230cbb73cc2e6822581f94c68cfac14a4032b48068fe124de8c25
```

Vivado completed route successfully. The final estimated route WNS was positive
at `0.283 ns`, and `top_route_status.rpt` reported `0` nets with routing
errors.

## Runtime Delta From Test 10

Test `11` keeps the successful test `10` path intact:

- `identifier_read()` remains skipped.
- SYS/RTIO clock switching remains skipped.
- `sed_spread_enable_write(0)` remains skipped.
- `reset_phy_write(1)` remains skipped.
- The analyzer remains skipped.
- The async RTIO error reporter remains skipped.

The only new probe is a read-only SYS_CRG current-clock CSR read immediately
before RTIO management startup:

```text
diag: before SYS_CRG current_clock_read probe
diag: SYS_CRG current_clock_read returned <value>
diag: after SYS_CRG current_clock_read probe
diag: before rtio_mgt startup
```

## Observed Boot Result

The user-provided populated-carrier UART log shows test `11` reaching the same
successful path as test `10` through:

- SZL gateware/runtime loading,
- runtime RAM and GIC initialization,
- skipped `identifier_read()`,
- I2C and both Kasli I/O expander initialization/service,
- Si5324 lock,
- skipped SYS/RTIO clock switch,
- network address assignment at IPv4 `192.168.1.75`,
- and skipped async RTIO error reporter startup.

It then prints:

```text
[     2.652919s]  INFO(runtime::comms): diag: skipping async RTIO error reporter task
[     2.654757s]  INFO(runtime::comms): diag: before SYS_CRG current_clock_read probe
```

No matching return marker was observed:

```text
diag: SYS_CRG current_clock_read returned <value>
diag: after SYS_CRG current_clock_read probe
```

This confirms that the immediate stop is inside, or at least during, this
read-only CSR transaction:

```rust
pl::csr::sys_crg::current_clock_read()
```

`current_clock` is a `CSRStatus` in `src/gateware/zynq_clocking.py`, so this is
not a side effect of an RTIO-core write or SED-spread configuration.

## Updated Interpretation

If boot hangs before or inside `current_clock_read`, the problem is broader
late PL/SYS_CRG CSR access, not only RTIO-core write behavior.

Test `11` did hang before the return marker. Together with earlier stops at
`identifier_read()`, `sys_crg::clock_switch_write(1)`, and
`rtio_core::sed_spread_enable_write(0)`, the working diagnosis is now that
populated-carrier failures are triggered by actual PL CSR bus transactions, not
by generated CSR metadata or by RTIO-core writes alone.

The next branch should not re-enable `rtio_core::reset_phy_write(1)`, analyzer,
or the async RTIO error reporter. It should test whether the PL CSR fabric is
unresponsive because the SYS clock is still on the skipped/default clock path.

## Next Experiment Design

Build test `12_dio0_dio1_forced_sys_clock_csr_probe` from the same 2-DIO JSON.

Keep the successful test `10`/`11` firmware path intact:

- keep `identifier_read()` skipped until the explicit probe point,
- keep firmware SYS/RTIO clock switching skipped,
- keep `sed_spread_enable_write(0)` skipped,
- keep `reset_phy_write(1)` skipped,
- keep analyzer skipped,
- keep async RTIO error reporter skipped.

Make one gateware-side clock-source change instead of issuing a CSR
`clock_switch_write(1)` from firmware: force or default the SYS_CRG clock switch
selection to the post-Si5324/main SYS clock path for this diagnostic image.

Then add only one explicit read-only CSR probe after network setup and before
RTIO management startup:

```text
diag: before forced-SYS SYS_CRG current_clock_read probe
diag: forced-SYS SYS_CRG current_clock_read returned <value>
diag: after forced-SYS SYS_CRG current_clock_read probe
diag: before rtio_mgt startup
```

Interpretation:

- If the read still hangs, the problem is not just the skipped SYS clock switch;
  the PS-to-PL CSR path is still not responding even when the SYS clock source
  is forced in gateware.
- If the read returns, the normal firmware-mediated SYS/RTIO clock-switch path
  is implicated. The next branch should test a forced-SYS build with a single
  RTIO-core write probe, still not the full `reset_phy_write(1)` sequence.

Do not re-enable `rtio_core::reset_phy_write(1)` for this branch. Test `09`
already showed that stacking an RTIO-core write back onto the path can hang the
populated-carrier boot.
