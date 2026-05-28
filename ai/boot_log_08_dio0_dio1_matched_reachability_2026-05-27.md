# Boot Log: 08 DIO0/DIO1 Matched Reachability

Date: 2026-05-27

Artifact under test:

```text
build/incremental_no_entangler/08_dio0_dio1_matched_reachability/boot.bin
```

Context: the Kasli-SoC is connected to the real experimental node. Do not run
automated physical reachability or control tests from this workspace unless the
user explicitly requests that exact operation.

## Result Summary

The 2-DIO matched reachability image boots much farther than the original early
hang. It loads SZL, gateware, and runtime, reaches Ethernet setup, prints the
configured network address, enters the control accept task, reports a 1 Gbit
full-duplex link, and keeps printing network poll heartbeats.

This means the populated Kasli-SoC is alive with the 2-DIO-only gateware and the
diagnostic runtime. The current log does not prove that the normal RTIO CSR
startup path is healthy, because this diagnostic image intentionally skips the
CSR accesses that previously hung.

## Key Boot Evidence

SZL loads gateware and runtime:

```text
[     0.107474s]  INFO(szl): Loading gateware
[     0.401540s] DEBUG(libboard_zynq::devc): Init postload FPGA
[     0.406831s]  INFO(szl): Loading runtime
[     0.542835s]  INFO(szl): Preparing for runtime
```

Runtime reaches early board initialization:

```text
[     0.000067s]  INFO(runtime): NAR3/Zynq7000 starting...
[     0.000126s]  INFO(runtime): diag: before ram init
[     0.004380s]  INFO(runtime): diag: after ram init
[     0.014014s]  INFO(runtime): diag: after gic enable
[     0.018875s]  INFO(runtime): diag: skipping identifier_read for populated-carrier CSR hang test
```

I2C and Kasli I/O expanders initialize:

```text
[     0.037512s]  INFO(libboard_zynq::i2c): PCA9548 detected
[     0.078724s]  INFO(runtime): diag: after io expander construct
[     0.131545s]  INFO(runtime): diag: after io expander init 0
[     0.184090s]  INFO(runtime): diag: after io expander init 1
[     0.201632s]  INFO(runtime): diag: after io expander service 1
```

RTIO clocking reaches Si5324 lock, but the diagnostic runtime skips the
SYS/RTIO clock switch:

```text
[     0.245580s]  INFO(runtime): diag: before rtio_clocking init
[     0.252818s]  INFO(runtime::rtio_clocking): using 125MHz reference to make 125MHz RTIO clock with PLL
[     3.252196s]  INFO(libboard_artiq::si5324):   ...locked
[     3.252208s]  INFO(runtime::rtio_clocking): diag: skipping SYS/RTIO clock switch for populated-carrier test
[     3.261489s]  INFO(runtime): diag: after rtio_clocking init
```

Networking starts and reports the expected address:

```text
[     3.303495s]  INFO(runtime::comms): network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
```

RTIO management is entered, but the diagnostic runtime skips the known-hanging
RTIO CSR writes:

```text
[     3.330833s]  INFO(runtime::rtio_mgt): diag: before rtio_mgt setup_sed_spread
[     3.344634s]  INFO(runtime::rtio_mgt): diag: skipping SED spread CSR write value 0
[     3.372844s]  INFO(runtime::rtio_mgt): diag: skipping rtio_core reset_phy CSR write
[     3.380483s]  INFO(runtime::comms): diag: after rtio_mgt startup
```

Control, management, moninj, and network polling become active:

```text
[     3.427877s]  INFO(runtime::comms): diag: after moninj start
[     3.440013s]  INFO(runtime::comms): diag: after kernel control start
[     3.451833s]  INFO(runtime::comms): diag: after mgmt start
[     3.464159s]  INFO(runtime::comms): diag: after control accept task spawn
[     3.470929s]  INFO(runtime::comms): diag: entering network poll loop
[     3.536647s]  INFO(runtime::comms): diag: control accept task entered
[     3.567974s]  INFO(runtime::comms): no idle kernel found
```

Ethernet link comes up and the runtime remains alive:

```text
[     4.999992s]  INFO(runtime::comms): diag: network poll heartbeat
[     6.984089s]  INFO(libboard_zynq::eth): eth: got Link { speed: S1000, duplex: Full }
[     9.999981s]  INFO(runtime::comms): diag: network poll heartbeat
[    44.999912s]  INFO(runtime::comms): diag: network poll heartbeat
```

## Interpretation

This is a successful boot/reachability-stage result for the narrow 2-DIO image.
The important progress markers are:

- the bitstream loads,
- runtime starts,
- I2C and I/O expanders initialize,
- the Si5324 locks,
- networking reaches `192.168.1.75`,
- the Ethernet link reports 1 Gbit full duplex,
- the control accept task starts,
- the network poll loop keeps running.

The remaining production blocker is still the RTIO/PL CSR path. This boot image
does not exercise the normal `identifier_read`, SYS/RTIO clock switch CSR write,
SED spread CSR write, RTIO PHY reset CSR write, async RTIO error reporter, or
analyzer startup. Those were skipped specifically to keep the populated node
reachable for diagnosis.

## Recommended Next Step

The next image should be a minimally less-skipped diagnostic build with the same
2-DIO JSON. Re-enable one skipped RTIO/PL CSR operation at a time, preserving the
UART breadcrumbs, so the exact first failing production CSR access is isolated
without risking uncontrolled physical tests.

Recommended order:

1. Keep `identifier_read` skipped, keep SYS/RTIO clock switch skipped, but
   re-enable only the RTIO management SED spread write.
2. If that boots, re-enable only the RTIO PHY reset write.
3. If that boots, re-enable analyzer startup.
4. If that boots, re-enable async RTIO error reporting.
5. Only after those pass, test the SYS/RTIO clock switch.
6. Leave `identifier_read` until late because it was the earliest original PL
   CSR hang and it blocks diagnosis before networking.

Host reachability checks should be run manually by the user from the appropriate
machine or interface connected to the real node, not automatically by the agent.
