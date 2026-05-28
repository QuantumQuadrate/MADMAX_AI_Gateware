# Boot Log: 19 DIO0/DIO1 Bootstrap AXI Write-Only Probe

Date: 2026-05-27

Artifact to boot:

```text
build/incremental_no_entangler/19_dio0_dio1_bootstrap_axi_write_only_probe/boot.bin
```

Source JSON:

```text
build/incremental_no_entangler/19_dio0_dio1_bootstrap_axi_write_only_probe/source.json
```

## Build Result

Packaged artifact:

```text
build/incremental_no_entangler/19_dio0_dio1_bootstrap_axi_write_only_probe/boot.bin
sha256 abd7250e2b19602df3110506ec67d52c4bd11caa542ce87f91c15b0b043b0313
```

Supporting outputs:

```text
top.bit     sha256 29a6e7ffefb6df67d01a61429f01178aafc23b6b4120fe843318a496e46be201
runtime.elf sha256 a9c7e26ff2bdd61a1eb5255cecf839ae2c3037a0ca58c23f0ba6594392376dd5
runtime.bin sha256 2458c614aed942df0d54c99d8323b9d951fecf0260ce216f012cea9d98b03e19
source JSON sha256 9b11fcdf7b08207219c5cb069f8bf0520590580273dc0f5b3cf418cc4bf608de
```

Vivado completed route and bitstream generation successfully. The final timing
report shows WNS `0.254 ns`, TNS `0.000 ns`, and `All user specified timing
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

The generated Verilog keeps standalone SYS_CRG on the bootstrap clock path by
default:

```text
reg sys_crg_storage_full = 1'd0;
```

The generated Rust configuration contains:

```text
has_csr_bridge_probe
bootstrap_axi_csr_timeout_probe
bootstrap_axi_csr_write_only_probe
has_sys_crg
has_rtio_core
hw_rev="v1.0"
rtio_frequency="125.0"
```

## Diagnostic Purpose

Experiment `19` keeps the two-DIO, no-Entangler, standalone-SYS_CRG shape from
experiment `18`, but removes all pre-write CSR reads from the post-network
diagnostic. The first intentional post-network PL/RTIO CSR transaction is
exactly one direct write:

```text
csr::rtio_core::sed_spread_enable_write(0)
```

Still skipped in this image:

- all `identifier_read()` calls
- SYS/RTIO clock-switch firmware write
- async RTIO error reporter task
- analyzer startup
- RTIO PHY reset CSR write
- Entangler logic
- additional EEM cards beyond DIO0 and DIO1

## Observed Boot Result

The user-provided populated-carrier boot log reaches runtime, initializes RAM,
GIC, I2C, both I/O expanders, Si5324, and Ethernet, then reaches the RTIO CSR
metadata preflight:

```text
[     2.622968s]  INFO(runtime::comms): network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
[     2.642919s]  INFO(runtime::comms): diag: skipping async RTIO error reporter task
[     2.644758s]  INFO(runtime::comms): diag: skipping identifier_read for experiment 19 bootstrap AXI write-only probe
[     2.655174s]  INFO(runtime::comms): diag: before rtio_mgt startup
[     2.661250s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=0x80000800 rtio_core=0x80001000
[     2.674356s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: generated CSR bases rtio=0x80002000 rtio_dma=0x80002800 rtio_moninj=0x80003800
[     2.687203s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: rtio_core base=0x80001000 reset=0x80001000 reset_phy=0x80001004 sed_spread_enable=0x80001008
[     2.712114s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: sys_crg base=0x80000800 current_clock=0x80000800 clock_switch=0x80000804
[     2.779297s]  INFO(runtime::rtio_mgt): diag: before rtio_mgt setup_sed_spread
[     2.786415s]  INFO(runtime::rtio_mgt): SED spreading disabled by default
[     2.793099s]  INFO(runtime::rtio_mgt): diag: experiment 19 write-only probe: no post-network PL CSR reads have been attempted before the decisive write
[     2.806639s]  INFO(runtime::rtio_mgt): diag: before experiment 19 bootstrap AXI write-only SED spread CSR write value 0 address=0x80001008
```

No later marker was observed:

```text
diag: after experiment 19 bootstrap AXI write-only SED spread CSR write value 0
diag: experiment 19 classification: after-write marker printed, so the ARM/PS AXI write completed
diag: after rtio_mgt setup_sed_spread
```

## Finding

Experiment `19` gives the decisive classification requested for the write-only
test: the UART stops after the before-write marker. Therefore the ARM/PS AXI
write to `csr::rtio_core::sed_spread_enable_write(0)` still did not receive a
completion response, even with the bootstrap-clocked AXI2CSR response-path
modification and with no earlier post-network PL CSR reads.

This does not yet prove whether the failed response is caused by the generic
AXI2CSR path itself or by the RTIO-core/sys-domain CSR target. The next
experiment should make the first post-network transaction a write to a
bootstrap-local dummy CSR sink that has no RTIO-core, SYS_CRG, identifier, or
sys-domain target dependency. Only after that local write returns should the
firmware optionally attempt the RTIO-core SED write as a secondary comparison.
