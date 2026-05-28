# Boot Log: 09 DIO0/DIO1 SED Spread Enabled

Date: 2026-05-27

Artifact under test:

```text
build/incremental_no_entangler/09_dio0_dio1_sed_spread_enabled/boot.bin
```

Context: the Kasli-SoC is connected to the real experimental node. Do not run
automated physical reachability or control tests from this workspace unless the
user explicitly requests that exact operation.

## Result Summary

The `09` image proves that the 2-DIO diagnostic runtime still reaches runtime,
I2C, I/O expander setup, Si5324 lock, skipped SYS/RTIO clock switch, and network
address assignment on the populated carrier. It then stops at the first
re-enabled RTIO-management CSR write:

```rust
csr::rtio_core::sed_spread_enable_write(0)
```

The decisive evidence is that the log prints:

```text
diag: before SED spread CSR write value 0
```

and does not print:

```text
diag: after SED spread CSR write value 0
```

That makes this a confirmed stop inside or immediately on return from the
`rtio_core::sed_spread_enable_write(0)` CSR transaction.

## Key Boot Evidence

SZL loads gateware and runtime:

```text
[     0.107501s]  INFO(szl): Loading gateware
[     0.403394s] DEBUG(libboard_zynq::devc): Init postload FPGA
[     0.408686s]  INFO(szl): Loading runtime
[     0.545743s]  INFO(szl): Preparing for runt...
```

Runtime reaches early board initialization:

```text
[     0.000067s]  INFO(runtime): NAR3/Zynq7000 starting...
[     0.000126s]  INFO(runtime): diag: before ram init
[     0.004371s]  INFO(runtime): diag: after ram init
[     0.014006s]  INFO(runtime): diag: after gic enable
[     0.018867s]  INFO(runtime): diag: skipping identifier_read for populated-carrier CSR hang test
```

I2C and Kasli I/O expanders initialize:

```text
[     0.037510s]  INFO(libboard_zynq::i2c): PCA9548 detected
[     0.078701s]  INFO(runtime): diag: after io expander construct
[     0.131496s]  INFO(runtime): diag: after io expander init 0
[     0.184055s]  INFO(runtime): diag: after io expander init 1
[     0.201598s]  INFO(runtime): diag: after io expander service 1
```

RTIO clocking reaches Si5324 lock, while the diagnostic runtime still skips the
SYS/RTIO clock switch:

```text
[     0.245867s]  INFO(runtime): diag: before rtio_clocking init
[     0.253104s]  INFO(runtime::rtio_clocking): using 125MHz reference to make 125MHz RTIO clock with PLL
[     0.624529s]  INFO(libboard_artiq::si5324): waiting for Si5324 lock...
[     2.581858s]  INFO(libboard_artiq::si5324):   ...locked
[     2.581871s]  INFO(runtime::rtio_clocking): diag: skipping SYS/RTIO clock switch for populated-carrier test
[     2.591150s]  INFO(runtime): diag: after rtio_clocking init
```

Networking reaches the expected configured address:

```text
[     2.633176s]  INFO(runtime::comms): network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
```

The runtime enters RTIO management startup and stops at the SED spread CSR
write:

```text
[     2.654757s]  INFO(runtime::comms): diag: before rtio_mgt startup
[     2.660833s]  INFO(runtime::rtio_mgt): diag: before rtio_mgt setup_sed_spread
[     2.669572s]  INFO(runtime::rtio_mgt): SED spreading disabled by default
[     2.674634s]  INFO(runtime::rtio_mgt): diag: before SED spread CSR write value 0
```

No `after SED spread CSR write value 0`, `after rtio_mgt setup_sed_spread`, or
later comms startup marker was observed.

## Interpretation

This is not a networking failure. The board has already printed
`network addresses` by the time it stops.

This is also not a failure of the 2-DIO JSON itself to load, because the same
image family already reached the control/network loop in `08` when this CSR
write was skipped.

The new result isolates the next confirmed populated-carrier stop to an
RTIO-core CSR access. Because the SYS/RTIO clock switch is still skipped in
this image, the stop may mean one of two things:

- `sed_spread_enable_write(0)` is the next inherently hanging RTIO-core CSR on
  the populated carrier.
- Any RTIO-core CSR write is unsafe in this diagnostic state because the
  SYS/RTIO clock switch was skipped, leaving the RTIO CSR fabric in a state
  where it does not respond cleanly.

In either case, do not proceed to re-enable `rtio_core::reset_phy_write(1)` yet.
The first re-enabled RTIO-core write did not return.

## Recommended Next Step

Build the next diagnostic image as `10` with:

- the same 2-DIO JSON,
- `identifier_read()` still skipped,
- SYS/RTIO clock switch still skipped,
- `sed_spread_enable_write(0)` skipped again, so the board can reach networking,
- `rtio_core::reset_phy_write(1)` still skipped,
- an added preflight diagnostic that reports the generated CSR addresses for
  the RTIO-core block and confirms whether the runtime believes the RTIO core is
  present before any RTIO-core write is attempted.

The immediate goal of `10` should be evidence collection, not re-enabling the
next CSR write. First confirm whether the RTIO-core CSR window and generated
CSR metadata match the bitstream packaged into this exact image, then decide
whether the next experiment should attack the SYS/RTIO clock switch path or the
RTIO-core CSR window directly.
