# Boot Log: 22 DIO0/DIO1 Standalone SYS_CRG Normal AXI Local Write Sink Probe

Date: 2026-05-27

Artifact to boot:

```text
build/incremental_no_entangler/22_dio0_dio1_standalone_sys_crg_normal_axi_local_write_sink_probe/boot.bin
```

Source JSON:

```text
build/incremental_no_entangler/22_dio0_dio1_standalone_sys_crg_normal_axi_local_write_sink_probe/source.json
```

## Build Result

Packaged artifact:

```text
build/incremental_no_entangler/22_dio0_dio1_standalone_sys_crg_normal_axi_local_write_sink_probe/boot.bin
sha256 3e717255426f5c95015497138e8fefba297a5e5de2fc1e25d50ba026aa4c50a1
```

Supporting outputs:

```text
top.bit     sha256 da4cf156f8d84742af2a0a5461fcd40038a48f209b5c7dce0e5221db76e18a80
runtime.elf sha256 3a85da4f07330cfafbd1e3b2032e42002c3f3c9ce82cec23e505414c58c8b207
runtime.bin sha256 3c1ae564e3835280c0b8df1e55d124b13f1616830234d16496e91ecc6e0d2304
source JSON sha256 735da03745f3c401b7c125747f86069a2ee999cd1f45741890de005679d14a6b
```

Vivado completed route and bitstream generation successfully. The final timing
report shows WNS `1.656 ns`, TNS `0.000 ns`, and `All user specified timing
constraints are met.` The route-status report shows `0` nets with routing
errors.

## Hardware Constraints

This artifact is for the real populated Node Kasli-SoC carrier hardware
revision `v1.0`. The parsed source JSON contains:

```text
hw_rev: v1.0
peripherals: DIO EEM0, DIO EEM1
Entangler: absent
extra EEM cards: absent
```

The generated Rust configuration contains:

```text
has_standalone_sys_write_sink
has_sys_crg
has_si5324
has_rtio_core
standalone_sys_local_write_sink_probe
hw_rev="v1.0"
rtio_frequency="125.0"
```

`bootstrap_axi_csr_timeout_probe`, `bootstrap_axi_csr_write_only_probe`,
`bootstrap_axi_local_write_sink_probe`, `ps_fclk_sys_probe`, and
`ps_fclk_local_write_sink_probe` are absent from the generated `rustc-cfg`.

## Diagnostic Purpose

Experiment `22` restores the standalone `SYS_CRG`/MMCM-driven generated `sys`
domain while keeping the normal, non-bootstrap-renamed AXI2CSR/CSR path. It
re-runs the experiment `21` local write-sink discipline against a dummy
generated CSRStorage target in the normal standalone `sys` domain.

The first intentional post-network PL CSR transaction is exactly one write:

```text
csr::standalone_sys_write_sink::value_write(0)
```

Still skipped in this image:

- all `identifier_read()` calls
- firmware SYS/RTIO clock-switch CSR write
- async RTIO error reporter task
- analyzer startup
- RTIO PHY reset CSR write
- Entangler logic
- additional EEM cards beyond DIO0 and DIO1
- bootstrap AXI2CSR diagnostic renaming
- PS-FCLK-only `sys` clocking

## Generated CSR Addresses

```text
identifier                            = 0x80000000
sys_crg                               = 0x80000800
rtio_core                             = 0x80001000
rtio_core::sed_spread_enable          = 0x80001008
standalone_sys_write_sink::value      = 0x80001800
rtio                                  = 0x80002000
rtio_dma                              = 0x80002800
cri_con                               = 0x80003000
rtio_moninj                           = 0x80003800
rtio_analyzer                         = 0x80004000
bootstrap_write_sink                  = absent
ps_fclk_write_sink                    = absent
```

## Expected UART Markers

```text
diag: skipping identifier_read for experiment 22 standalone-SYS local write sink probe
diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=0x80000800 rtio_core=0x80001000
diag: rtio csr preflight: standalone_sys_write_sink base=0x80001800 value=0x80001800
diag: rtio csr preflight: runtime cfg has_sys_crg=true
diag: experiment 22 standalone-SYS local write sink probe: no post-network PL CSR reads have been attempted before the decisive local write
diag: before experiment 22 standalone-SYS local write sink CSR write value 0 address=0x80001800
diag: after experiment 22 standalone-SYS local write sink CSR write value 0
diag: after rtio_mgt setup_sed_spread
diag: entering network poll loop
```

## Observed Boot Result

The user-provided populated-carrier boot log shows SZL loading gateware and
runtime successfully. Runtime then reaches RAM init, GIC enable, I2C init, both
I/O expander init/service paths, log setup, `rtio_clocking::init()`, Si5324
lock, network address setup, and RTIO management preflight.

Key clocking and network markers:

```text
diag: before rtio_clocking init
runtime::rtio_clocking: using 125MHz reference to make 125MHz RTIO clock with PLL
libboard_artiq::si5324:   ...locked
runtime::rtio_clocking: diag: skipping SYS/RTIO clock switch for populated-carrier test
diag: after rtio_clocking init
network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
```

Key generated-address preflight markers:

```text
diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=0x80000800 rtio_core=0x80001000
diag: rtio csr preflight: generated CSR bases rtio=0x80002000 rtio_dma=0x80002800 rtio_moninj=0x80003800
diag: rtio csr preflight: rtio_core base=0x80001000 reset=0x80001000 reset_phy=0x80001004 sed_spread_enable=0x80001008
diag: rtio csr preflight: sys_crg base=0x80000800 current_clock=0x80000800 clock_switch=0x80000804
diag: rtio csr preflight: standalone_sys_write_sink base=0x80001800 value=0x80001800
diag: rtio csr preflight: runtime cfg has_rtio_core=true
diag: rtio csr preflight: runtime cfg has_sys_crg=true
```

The decisive sequence reached the before-local-write marker and did not print
the after-local-write marker:

```text
diag: experiment 22 standalone-SYS local write sink probe: no post-network PL CSR reads have been attempted before the decisive local write
diag: before experiment 22 standalone-SYS local write sink CSR write value 0 address=0x80001800
```

No `after experiment 22 standalone-SYS local write sink CSR write`, `after
rtio_mgt setup_sed_spread`, `after rtio_mgt startup`, management/control
startup, or network poll-loop marker was observed after that write attempt.

## Classification

Observed classification: case `1`.

The boot stops after the before-local-write marker. Restoring standalone
`SYS_CRG`/MMCM-driven `sys` is enough to break even a dummy generated
CSRStorage write on the normal, non-bootstrap-renamed AXI2CSR path.

Classify the populated-carrier boot as:

1. Stops after the before-local-write marker: restoring standalone
   `SYS_CRG`/MMCM-driven `sys` is enough to break even a dummy generated
   CSRStorage write on the normal AXI2CSR path.
2. Prints the after-local-write marker and continues: standalone `SYS_CRG` plus
   normal AXI2CSR is not sufficient to reproduce the experiment `20` hang.
   Compare against experiments `18`-`20` for bootstrap AXI2CSR rename and CSR
   ordering effects.
3. Any later hang after the after-local-write marker is secondary for this
   experiment, because the decisive transaction already completed.

## Finding

Experiment `22` fails at the first intentional post-network PL CSR transaction:

```text
csr::standalone_sys_write_sink::value_write(0)
```

This is a dummy local `CSRStorage(32)` target at `0x80001800`, not `rtio_core`,
not `sys_crg`, and not a CSR read. Therefore the hang does not require:

- Entangler logic
- extra EEM cards beyond DIO0/DIO1
- `identifier_read()`
- async RTIO error reporting
- analyzer startup
- RTIO PHY reset
- an RTIO-core SED-spread target
- the experiment `18`-`20` bootstrap AXI2CSR clock-domain rename

Experiment `21` passed the same dummy generated CSRStorage write discipline
with PS-FCLK-driven `sys` and the normal AXI2CSR path. Experiment `22` changes
that back to standalone `SYS_CRG`/MMCM-driven `sys` while keeping normal
AXI2CSR, and the dummy write hangs. This strongly implicates the standalone
`SYS_CRG`/MMCM/reset/clock-domain integration or the PS GP AXI to generated CSR
response path when that CSR fabric is clocked by standalone `sys`.

The preflight lines above are generated address/cfg prints, not volatile PL CSR
reads. They do not weaken the "no PL CSR reads before the decisive write"
discipline.

## Next Diagnostic Direction

The next useful experiment should keep the same local dummy write sink and vary
only the standalone `sys` clock/reset/AXI handshake environment. Useful
directions:

- add an AXI/CSR response timeout or observer that does not depend on a
  pre-write PL CSR read,
- hold the standalone `sys` path on the bootstrap MMCM input while keeping
  AXI2CSR normal,
- add a minimal generated CSR write sink as early as possible in the CSR list to
  check whether address position matters,
- instrument whether the AXI2CSR write reaches the sys-domain CSR bus before
  the ARM/PS waits forever for completion.

## Artifact Bundle

The archive contains:

```text
boot.bin
top.bit
runtime.elf
runtime.bin
source.json
pl.rs
rustc-cfg
mem.rs
top_timing.rpt
top_route_status.rpt
top_drc.rpt
boot.bif
build-manifest.txt
```
