# Boot Log: 17 DIO0/DIO1 Bootstrap SED Spread No-Identifier Probe

Date: 2026-05-27

Artifact to boot:

```text
build/incremental_no_entangler/17_dio0_dio1_bootstrap_sed_spread_no_ident_probe/boot.bin
```

Source JSON:

```text
build/generated/experiment_17_dio0_dio1_bootstrap_sed_spread_no_ident_probe.json
```

## Build Result

Packaged artifact:

```text
build/incremental_no_entangler/17_dio0_dio1_bootstrap_sed_spread_no_ident_probe/boot.bin
sha256 c2f76c246a1ceabd7624a4915b9a53ff1b38096559d39b4a54222ed277495a8b
```

Supporting outputs:

```text
top.bit     sha256 54d26952ff3d14fef8364142e224c38814b8d031061cf06a244041f8835a24e6
runtime.elf sha256 22ee9779a4ac783986a1cd56272734cef9aab6cb306765a08aee522848f6f69c
runtime.bin sha256 cb8e3d4fd85f49155b5307f5caac73c8813a85cd4ad673fbe5f3fece1bcfca86
source JSON sha256 0b5cb2e767853bf1534a17100c7beaa5169779ca1abdb148b31ab3b9412cb0eb
```

Vivado completed route and bitstream generation successfully. The final timing
report shows WNS `0.234 ns`, TNS `0.000 ns`, and `All user specified timing
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

## Diagnostic Purpose

Experiment `17` keeps the narrow two-DIO no-Entangler shape from experiments
`13` through `16`. It also keeps standalone SYS_CRG present with the
`clock_switch` CSR reset/default low, skips the firmware SYS/RTIO clock-switch
write, and skips every `identifier_read()` call.

The intended first post-network PL/RTIO CSR transaction is:

```text
csr::rtio_core::sed_spread_enable_write(0)
```

Still skipped in this image:

- all `identifier_read()` calls
- SYS/RTIO clock-switch firmware write
- RTIO PHY reset CSR write
- analyzer startup
- async RTIO error reporter task
- Entangler logic
- additional EEM cards beyond DIO0 and DIO1

Expected decisive UART markers:

```text
diag: skipping identifier_read for experiment 17 bootstrap SED probe
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

## Observed Boot Result

The user-provided populated-carrier boot log reaches runtime, initializes RAM,
GIC, I2C, both I/O expanders, Si5324, and Ethernet, then reaches the RTIO CSR
preflight markers:

```text
[     2.633344s]  INFO(runtime::comms): network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
[     2.652920s]  INFO(runtime::comms): diag: skipping async RTIO error reporter task
[     2.654757s]  INFO(runtime::comms): diag: skipping identifier_read for experiment 17 bootstrap SED probe
[     2.664218s]  INFO(runtime::comms): diag: before rtio_mgt startup
[     2.670294s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=0x80000800 rtio_core=0x80001000
[     2.696247s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: rtio_core base=0x80001000 reset=0x80001000 reset_phy=0x80001004 sed_spread_enable=0x80001008
[     2.777145s]  INFO(runtime::rtio_mgt): diag: clock preflight: SYS/RTIO clock switch remains skipped in this diagnostic image
[     2.788342s]  INFO(runtime::rtio_mgt): diag: before rtio_mgt setup_sed_spread
[     2.797081s]  INFO(runtime::rtio_mgt): SED spreading disabled by default
[     2.802143s]  INFO(runtime::rtio_mgt): diag: before bootstrap-SYS SED spread CSR write value 0 address=0x80001008
```

No `after bootstrap-SYS SED spread CSR write value 0`, `after rtio_mgt
setup_sed_spread`, `after rtio_mgt startup`, control-task, or network heartbeat
marker was observed.

## Finding

Experiment `17` confirms that the post-network hang is not caused by the
explicit `identifier_read()` probe. With all identifier reads skipped, the
runtime still blocks on the first intentional PL/RTIO CSR transaction:

```text
csr::rtio_core::sed_spread_enable_write(0)
```

The hang occurs while standalone SYS_CRG is still held on its bootstrap clock
path (`sys_crg_storage_full = 1'd0`) and while the firmware SYS/RTIO
clock-switch write remains skipped. This points away from the identifier block
as the unique culprit and toward a broader post-network AXI/CSR transaction
problem involving the standalone SYS_CRG/MMCM-driven `sys` fabric or the
RTIO-core CSR bank under the populated real Node carrier conditions.

The next useful diagnostic should avoid another plain blocking CSR access if
the goal is to distinguish an AXI/CSR bridge wait from RTIO-core-local behavior.
