# Boot Log: 23 DIO0/DIO1 Standalone SYS_CRG Bootstrap-Input Normal AXI Local Write Sink Probe

Date: 2026-05-27

Artifact to boot:

```text
build/incremental_no_entangler/23_dio0_dio1_standalone_sys_crg_bootstrap_input_normal_axi_local_write_sink_probe/boot.bin
```

Source JSON:

```text
build/incremental_no_entangler/23_dio0_dio1_standalone_sys_crg_bootstrap_input_normal_axi_local_write_sink_probe/source.json
```

## Build Result

Packaged artifact:

```text
build/incremental_no_entangler/23_dio0_dio1_standalone_sys_crg_bootstrap_input_normal_axi_local_write_sink_probe/boot.bin
sha256 24519843499be5871adfb5ff1de901d3c06d9364c22b2570a3ab32dcdd1fca57
```

Supporting outputs:

```text
top.bit     sha256 3ebc1651b3c2c390b12cd49148bd87d4bc0b413f8f33f6fa16cb19f5b50b9d82
runtime.elf sha256 7fa68073babac24a548e0c81e3a1da8d5952f1ef1e98a645ae1f75439d3d12d8
runtime.bin sha256 927dee40dc2bee18bd5e0b6e09e6d23492d769198c01499b0c44a3216ca2b41e
source JSON sha256 59e9b54324664403140131a9d6e91ed9cc61cf9ecc05392bc210ab06ad5d9468
```

The archive also includes `pl.rs`, `rustc-cfg`, `mem.rs`, `boot.bif`,
`top_timing.rpt`, `top_route_status.rpt`, `top_drc.rpt`, `top.v`,
`build-manifest.txt`, and `SHA256SUMS`.

Vivado completed route and bitstream generation successfully. The final timing
report shows WNS `1.043 ns`, TNS `0.000 ns`, and `All user specified timing
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
sys_crg_bootstrap_input_probe
hw_rev="v1.0"
rtio_frequency="125.0"
```

`bootstrap_axi_csr_timeout_probe`, `bootstrap_axi_csr_write_only_probe`,
`bootstrap_axi_local_write_sink_probe`, `ps_fclk_sys_probe`, and
`ps_fclk_local_write_sink_probe` are absent from the generated `rustc-cfg`.

## Diagnostic Purpose

Experiment `23` keeps standalone `SYS_CRG` present and keeps the normal,
non-bootstrap-renamed AXI2CSR/CSR path. It re-runs the experiment `22` dummy
local `CSRStorage(32)` write-sink discipline, but forces the SYS_CRG MMCM input
selector onto the bootstrap input.

Generated `top.v` evidence:

```text
assign sys_crg_mmcm_clkin_sel = 1'd0;
assign sys_crg_mmcm_reset = 1'd0;
CLKIN1 = clk_synth_se_buf
CLKIN2 = bootstrap_clk
CLKINSEL = sys_crg_mmcm_clkin_sel
```

With the Xilinx MMCM input selector, `CLKINSEL=0` selects `CLKIN2`, so this
variant holds the standalone SYS_CRG/MMCM on `bootstrap_clk` while leaving the
CSR fabric in the generated `sys` domain.

The first intentional post-network PL CSR transaction is exactly one write:

```text
csr::standalone_sys_write_sink::value_write(0)
```

Still skipped in this image:

- all `identifier_read()` calls before the decisive write
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
sys_crg::current_clock                = 0x80000800
sys_crg::clock_switch                 = 0x80000804
rtio_core                             = 0x80001000
rtio_core::sed_spread_enable          = 0x80001008
standalone_sys_write_sink::value      = 0x80001800
bootstrap_write_sink                  = absent
ps_fclk_write_sink                    = absent
```

## Expected UART Markers

```text
diag: skipping identifier_read for experiment 23 standalone-SYS bootstrap-input local write sink probe
diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=0x80000800 rtio_core=0x80001000
diag: rtio csr preflight: standalone_sys_write_sink base=0x80001800 value=0x80001800
diag: rtio csr preflight: runtime cfg has_sys_crg=true
diag: clock preflight: generated config sys_crg_bootstrap_input_probe=true
diag: experiment 23 standalone-SYS bootstrap-input local write sink probe: no post-network PL CSR reads have been attempted before the decisive local write
diag: before experiment 23 standalone-SYS bootstrap-input local write sink CSR write value 0 address=0x80001800
diag: after experiment 23 standalone-SYS bootstrap-input local write sink CSR write value 0
diag: after rtio_mgt setup_sed_spread
diag: entering network poll loop
```

## Expected Classification

1. Hangs before or at the dummy write like experiment `22`: standalone
   SYS_CRG/MMCM/reset integration itself, or AXI2CSR crossing into
   SYS_CRG-driven `sys`, is enough to break CSR write completion.
2. Prints the after-write marker: experiment `22` failure is likely tied to the
   main/external/SI5324/CDR SYS_CRG input path or clock-switch/input-selection
   behavior, not merely SYS_CRG existence.
3. Any later hang after the after-write marker is secondary for this experiment.

## Hardware Boot Result

The user-provided populated-carrier boot log shows SZL loading gateware and
runtime successfully. Runtime reaches RAM init, GIC enable, I2C init, both I/O
expander init/service paths, log setup, `rtio_clocking::init()`, Si5324 lock,
network address setup, and RTIO management preflight.

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
diag: clock preflight: generated config sys_crg_bootstrap_input_probe=true
```

The decisive sequence reached the before-local-write marker and did not print
the after-local-write marker:

```text
diag: experiment 23 standalone-SYS bootstrap-input local write sink probe: no post-network PL CSR reads have been attempted before the decisive local write
diag: before experiment 23 standalone-SYS bootstrap-input local write sink CSR write value 0 address=0x80001800
```

No `after experiment 23 standalone-SYS bootstrap-input local write sink CSR
write`, `after rtio_mgt setup_sed_spread`, `after rtio_mgt startup`, or network
poll-loop marker was observed after that write attempt.

## Classification

Observed classification: case `1`.

The boot stops after the before-local-write marker. Holding the standalone
SYS_CRG/MMCM on the bootstrap input does not restore generated CSR write
completion. The failing condition therefore does not require the main/external
SI5324/CDR SYS_CRG input path, nor the firmware clock-switch CSR write. A
standalone SYS_CRG/MMCM/reset integration, or the AXI2CSR crossing into
SYS_CRG-driven `sys`, remains sufficient to wedge the first dummy generated
CSRStorage write.

## Finding

Experiment `21` completed a dummy generated CSR write when `sys` was driven
directly from PS FCLK and AXI2CSR was normal. Experiment `22` hung on the same
normal generated `sys`-domain dummy write after restoring standalone
SYS_CRG/MMCM-driven `sys` from the normal external/main input path. Experiment
`23` kept standalone SYS_CRG and normal AXI2CSR, forced the MMCM onto the
bootstrap clock input, and still hung on the dummy write.

This narrows the suspect away from the external/main SI5324/CDR input path and
toward standalone SYS_CRG/MMCM/reset integration itself, or the PS GP AXI to
generated CSR completion path when the CSR fabric is clocked by standalone
SYS_CRG-driven `sys`.
