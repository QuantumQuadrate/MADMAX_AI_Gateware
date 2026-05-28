# Boot Log: 10 DIO0/DIO1 RTIO CSR Preflight

Date: 2026-05-27

Artifact under test:

```text
build/incremental_no_entangler/10_dio0_dio1_rtio_csr_preflight/boot.bin
```

Context: the Kasli-SoC is connected to the real experimental node. Do not run
automated physical reachability or control tests from this workspace unless the
user explicitly requests that exact operation.

## Result Summary

The `10` image restores the reachable `08` behavior after the `09` SED spread
CSR hang, while successfully printing all new metadata-only RTIO CSR and clock
preflight diagnostics.

The populated carrier reaches:

- SZL gateware and runtime loading,
- runtime RAM and GIC initialization,
- skipped `identifier_read()`,
- I2C and both Kasli I/O expander initialization/service,
- Si5324 lock,
- skipped SYS/RTIO clock switch,
- network address assignment at `192.168.1.75`,
- all RTIO CSR/clock preflight metadata,
- skipped SED spread CSR write,
- skipped RTIO PHY reset CSR write,
- device-map setup,
- moninj, kernel-control, management, and control accept task startup,
- network polling and repeated heartbeats through at least `19.999962s`,
- Ethernet link up at 1 Gbit full duplex.

This confirms that the new metadata-only preflight logs are safe on the
populated carrier and that skipping the first known-hanging RTIO-core write
restores the reachable network/control path.

## Key Boot Evidence

SZL loads gateware and runtime:

```text
[     0.107491s]  INFO(szl): Loading gateware
[     0.401621s] DEBUG(libboard_zynq::devc): Init postload FPGA
[     0.406911s]  INFO(szl): Loading runtime
[     0.544637s]  INFO(szl): Preparing for runt...
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
[     0.037511s]  INFO(libboard_zynq::i2c): PCA9548 detected
[     0.078721s]  INFO(runtime): diag: after io expander construct
[     0.131548s]  INFO(runtime): diag: after io expander init 0
[     0.184101s]  INFO(runtime): diag: after io expander init 1
[     0.201642s]  INFO(runtime): diag: after io expander service 1
```

RTIO clocking reaches Si5324 lock, with SYS/RTIO clock switching still skipped:

```text
[     0.245867s]  INFO(runtime): diag: before rtio_clocking init
[     0.253107s]  INFO(runtime::rtio_clocking): using 125MHz reference to make 125MHz RTIO clock with PLL
[     2.581840s]  INFO(libboard_artiq::si5324):   ...locked
[     2.581852s]  INFO(runtime::rtio_clocking): diag: skipping SYS/RTIO clock switch for populated-carrier test
[     2.591133s]  INFO(runtime): diag: after rtio_clocking init
```

Networking reaches the expected configured address:

```text
[     2.633174s]  INFO(runtime::comms): network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
```

The RTIO CSR and clock preflight metadata prints completely:

```text
[     2.660833s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=0x80000800 rtio_core=0x80001000
[     2.673940s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: generated CSR bases rtio=0x80001800 rtio_dma=0x80002000 rtio_moninj=0x80003000
[     2.686787s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: rtio_core base=0x80001000 reset=0x80001000 reset_phy=0x80001004 sed_spread_enable=0x80001008
[     2.700848s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: rtio_core sizes reset=1 reset_phy=1 sed_spread_enable=1
[     2.711698s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: sys_crg base=0x80000800 current_clock=0x80000800 clock_switch=0x80000804
[     2.724024s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: runtime cfg has_rtio_core=true
[     2.732703s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: runtime cfg has_sys_crg=true
[     2.741210s]  INFO(runtime::rtio_mgt): diag: clock preflight: generated rtio_frequency=125.0 MHz
[     2.749976s]  INFO(runtime::rtio_mgt): diag: clock preflight: generated clock_frequency=125000000 Hz
[     2.759091s]  INFO(runtime::rtio_mgt): diag: clock preflight: generated config has_si5324=true
[     2.767684s]  INFO(runtime::rtio_mgt): diag: clock preflight: SYS/RTIO clock switch remains skipped in this diagnostic image
```

SED spread and RTIO PHY reset are skipped, and RTIO management startup returns:

```text
[     2.787620s]  INFO(runtime::rtio_mgt): SED spreading disabled by default
[     2.792682s]  INFO(runtime::rtio_mgt): diag: skipping SED spread CSR write value 0 after 09 populated-carrier hang
[     2.803011s]  INFO(runtime::rtio_mgt): diag: skipped SED spread CSR target address=0x80001008
[     2.811519s]  INFO(runtime::rtio_mgt): diag: after rtio_mgt setup_sed_spread
[     2.825406s]  INFO(runtime::rtio_mgt): diag: after rtio_mgt drtio startup
[     2.832176s]  INFO(runtime::rtio_mgt): diag: skipping rtio_core reset_phy CSR write
[     2.839815s]  INFO(runtime::comms): diag: after rtio_mgt startup
```

Control and network loop startup are reached:

```text
[     2.866376s]  INFO(runtime::comms): diag: after setup_device_map
[     2.872365s]  INFO(runtime::comms): diag: skipping analyzer start for control-loop reachability test
[     2.887209s]  INFO(runtime::comms): diag: after moninj start
[     2.899339s]  INFO(runtime::comms): diag: after kernel control start
[     2.911165s]  INFO(runtime::comms): diag: after mgmt start
[     2.923491s]  INFO(runtime::comms): diag: after control accept task spawn
[     2.930260s]  INFO(runtime::comms): diag: entering network poll loop
[     2.995978s]  INFO(runtime::comms): diag: control accept task entered
```

The runtime remains alive and Ethernet reports 1 Gbit full duplex:

```text
[     4.999991s]  INFO(runtime::comms): diag: network poll heartbeat
[     5.943091s]  INFO(libboard_zynq::eth): eth: got Link { speed: S1000, duplex: Full }
[     9.999981s]  INFO(runtime::comms): diag: network poll heartbeat
[    14.999972s]  INFO(runtime::comms): diag: network poll heartbeat
[    19.999962s]  INFO(runtime::comms): diag: network poll heartbeat
```

## Interpretation

This is a successful diagnostic result for test `10`.

It shows that the RTIO-core/SYS_CRG generated metadata is internally consistent
with the archived `pl.rs` constants for this 2-DIO build:

```text
identifier=0x80000000
sys_crg=0x80000800
rtio_core=0x80001000
rtio=0x80001800
rtio_dma=0x80002000
rtio_moninj=0x80003000
sed_spread_enable=0x80001008
```

It also confirms that simply reporting those generated addresses and target
configuration does not trigger the populated-carrier hang. The hang in `09`
therefore remains tied to executing the RTIO-core CSR transaction itself:

```rust
csr::rtio_core::sed_spread_enable_write(0)
```

The warning about missing `device_map` is not the boot blocker. It appears
after `rtio_mgt startup` and the runtime continues into control/network loop
execution.

## Recommended Next Step

Do not re-enable `rtio_core::reset_phy_write(1)` yet.

The next useful diagnostic branch is to decide whether the confirmed CSR hangs
are caused by:

- any PL/RTIO CSR transaction after the populated carrier is attached,
- write transactions specifically,
- the SYS/RTIO clock domain not being switched,
- or the RTIO fabric being held/reset/unclocked despite the generated CSR map
  being correct.

A good `11` test would keep the `10` reachable path intact and add one narrow,
late, explicitly labeled probe at a time. The least disruptive next probe is a
read-only SYS_CRG current-clock probe immediately before RTIO management, with
breadcrumbs before and after it. If that read hangs, the failure is broader than
RTIO-core writes. If it returns, the next controlled probe can target the
SYS/RTIO clock-switch sequence separately from RTIO-core writes.
