# Boot Log: 20 DIO0/DIO1 Bootstrap AXI Local Write Sink Probe

Date: 2026-05-27

Artifact to boot:

```text
build/incremental_no_entangler/20_dio0_dio1_bootstrap_axi_local_write_sink_probe/boot.bin
```

Source JSON:

```text
build/incremental_no_entangler/20_dio0_dio1_bootstrap_axi_local_write_sink_probe/source.json
```

## Build Result

Packaged artifact:

```text
build/incremental_no_entangler/20_dio0_dio1_bootstrap_axi_local_write_sink_probe/boot.bin
sha256 e4ddef54f6ea776804fc15b37c6824d095dbb975ee9e8cfe55581d872bfe61e7
```

Supporting outputs:

```text
top.bit     sha256 b2256b9b7ab01028002cf06404b88783a6af2dbfc2a21e339bcac1d163dcc501
runtime.elf sha256 d7edd424c2c03f16b154aac62bce985ba5d905dfcd9261e6914c22e2941768fd
runtime.bin sha256 70a582d6fc37ad16f8c8a86ae64ac7143b860b2792a9eec176efa202a574716a
source JSON sha256 f871b590e25ff67b806146ff01ebfdbc96c9aea2947077845a7af9be9393481a
```

Vivado completed route and bitstream generation successfully. The final timing
report shows WNS `0.299 ns`, TNS `0.000 ns`, and `All user specified timing
constraints are met.` The route-status report shows `0` nets with routing
errors.

## Hardware Constraints

This artifact is for the real Node Kasli-SoC carrier hardware revision `v1.0`.
The parsed source JSON contains:

```text
hw_rev: v1.0
peripherals: DIO EEM0, DIO EEM1
Entangler: absent
extra EEM cards: absent
```

The generated Verilog keeps standalone SYS_CRG present and leaves the
`clock_switch` CSR reset/default low:

```text
reg sys_crg_storage_full = 1'd0;
```

The generated Rust configuration contains:

```text
has_bootstrap_write_sink
bootstrap_axi_csr_timeout_probe
bootstrap_axi_local_write_sink_probe
has_sys_crg
has_rtio_core
hw_rev="v1.0"
rtio_frequency="125.0"
```

`has_csr_bridge_probe` and `bootstrap_axi_csr_write_only_probe` are absent from
the generated `rustc-cfg`.

## Diagnostic Purpose

Experiment `20` separates a generic PS AXI to bootstrap-clocked CSR
write-response failure from an RTIO-core/sys-domain CSR target failure.

The first intentional post-network PL CSR transaction is exactly one direct
write to the bootstrap-local CSR sink:

```text
csr::bootstrap_write_sink::value_write(0)
```

Only after the after-local-write marker does firmware attempt the secondary
comparison write:

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
- `csr_bridge_probe` logic

## Generated CSR Addresses

```text
bootstrap_write_sink::value = 0x80001800
rtio_core::sed_spread_enable = 0x80001008
sys_crg::clock_switch = 0x80000804
```

## Expected UART Markers

```text
diag: experiment 20 local write sink probe: no post-network PL CSR reads have been attempted before the decisive local write
diag: before experiment 20 bootstrap-local write sink CSR write value 0 address=0x80001800
diag: after experiment 20 bootstrap-local write sink CSR write value 0
diag: before experiment 20 secondary RTIO-core SED spread CSR write value 0 address=0x80001008
diag: after experiment 20 secondary RTIO-core SED spread CSR write value 0
```

## Observed Boot Result

The user-provided populated-carrier boot log reaches SZL, loads gateware and
runtime, initializes RAM, GIC, I2C, both I/O expanders, locks the Si5324, and
prints Ethernet addresses:

```text
network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
```

It then reaches the experiment `20` metadata preflight and confirms the generated
bootstrap-local sink address:

```text
diag: rtio csr preflight: bootstrap_write_sink base=0x80001800 value=0x80001800
diag: clock preflight: SYS/RTIO clock switch remains skipped in this diagnostic image
diag: before rtio_mgt setup_sed_spread
SED spreading disabled by default
diag: experiment 20 local write sink probe: no post-network PL CSR reads have been attempted before the decisive local write
diag: before experiment 20 bootstrap-local write sink CSR write value 0 address=0x80001800
```

No later marker was observed:

```text
diag: after experiment 20 bootstrap-local write sink CSR write value 0
diag: before experiment 20 secondary RTIO-core SED spread CSR write value 0 address=0x80001008
diag: after experiment 20 secondary RTIO-core SED spread CSR write value 0
diag: after rtio_mgt setup_sed_spread
```

## Finding

Experiment `20` stops on the first intentional post-network PL CSR transaction:

```text
csr::bootstrap_write_sink::value_write(0)
```

That target is a dummy `CSRStorage(32)` added as `bootstrap_write_sink` and
renamed into the `bootstrap` clock domain. In this variant, the AXI2CSR bridge
is also renamed into the `bootstrap` domain. Therefore this result is stronger
than experiment `19`: the hang is not specific to `rtio_core`, the SYS_CRG
status/control CSRs, the identifier CSR, the SED-spread register, or a
sys-domain RTIO target.

The current best classification is a generic PS AXI to generated PL CSR write
completion failure in this diagnostic image. The runtime reaches networking and
all metadata-only address prints, but the ARM/PS never reaches the instruction
after the write to `0x80001800`, so the CSR write does not complete from the
CPU's point of view.

This points next at the common transaction path rather than the individual CSR
target:

- PS GP AXI to AXI2CSR write/response completion
- CSR bus address decode or acknowledge generation for generated CSR banks
- reset/clock availability for the bootstrap CSR path on the populated carrier
- any integration difference introduced by the diagnostic AXI2CSR/bootstrap
  renaming or CSR-device ordering

## Classification

1. Observed: stops after the before-local-write marker. A generic PS
   AXI/AXI2CSR/bootstrap CSR write still does not complete.
2. Prints the after-local-write marker, then stops on the secondary RTIO write:
   bootstrap-local writes complete; the hang is specific to the
   RTIO-core/sys-domain CSR target path.
3. Prints both after-write markers: compare generated CSR ordering/addresses
   and gateware changes against experiment `19`.
