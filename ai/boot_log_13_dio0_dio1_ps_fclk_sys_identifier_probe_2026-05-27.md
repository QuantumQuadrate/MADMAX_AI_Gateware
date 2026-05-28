# Boot Log: 13 DIO0/DIO1 PS-FCLK SYS Identifier Probe

Date: 2026-05-27

Artifact to boot:

```text
build/incremental_no_entangler/13_dio0_dio1_ps_fclk_sys_identifier_probe/boot.bin
```

Source JSON:

```text
build/generated/experiment_13_dio0_dio1_ps_fclk_sys_identifier_probe.json
```

## Build Result

Packaged artifact:

```text
build/incremental_no_entangler/13_dio0_dio1_ps_fclk_sys_identifier_probe/boot.bin
sha256 4d8f1e2b94d37a4f868f66a6796e7f78d63b93b4b8bbf1f4f3f249e3dbf0f9d3
```

Supporting outputs:

```text
top.bit     sha256 0bac3bb608b1762ce08b0f7c9de5b0f1697c1e6a2a4a8c55cb70abbeae1283bb
runtime.elf sha256 adc14c8fa67e9031a6f6568f5587ed7488d19ae3f534d48d5da5e2767d6b1797
runtime.bin sha256 b3cd17a5f7a752fc2075ec4dc68e106107c59e227657214e4a49fcedc0071c8f
source JSON sha256 71f1cbc581fe06011df98e72e73a84453aeccab93619bd0c59a6e63e3753d791
```

Vivado completed route and bitstream generation successfully. The final timing
report shows WNS `1.907 ns` and `All user specified timing constraints are
met.` The route-status report shows `0` nets with routing errors.

## Diagnostic Purpose

Test `13` is a stronger isolation image for the CSR hang:

- the standalone gateware uses the Zynq PS FCLK as the `sys` clock source,
- `sys4x` is aliased to `sys` only so the two-DIO diagnostic image can build,
- no standalone `sys_crg` CSR block is generated,
- no Si5324 or Si549 clock-synthesizer config is generated,
- early `identifier_read()` remains skipped,
- firmware SYS/RTIO clock switching remains skipped,
- SED spread, RTIO PHY reset, analyzer startup, and async RTIO error reporting remain skipped,
- one explicit `identifier_read()` CSR probe is performed after networking setup.

This image is not a normal RTIO timing image. It is only meant to answer whether
the PS-to-PL CSR path works when the main PL `sys` fabric is not dependent on
the standalone SYS_CRG/MMCM clock path.

Expected decisive markers:

```text
diag: before PS-FCLK identifier_read CSR probe
diag: PS-FCLK identifier_read returned <ident>
diag: after PS-FCLK identifier_read CSR probe
diag: before rtio_mgt startup
```

## Interpretation Guide

If the boot reaches the `identifier_read returned` and `after` markers, the
basic PS-to-PL CSR path can respond with the PS-FCLK-driven diagnostic fabric.
That would strongly implicate the original standalone SYS_CRG/MMCM/reset path.

If it stops after:

```text
diag: before PS-FCLK identifier_read CSR probe
```

then the problem is lower than the standalone SYS_CRG read-only status CSR. It
would mean even the identifier CSR transaction can hang with the diagnostic
fabric clocked from PS FCLK.

## Observed Boot Result

The user-provided populated-carrier UART log shows this image booting
successfully through the decisive PS-FCLK CSR probe and into the long-running
network loop.

Key successful markers:

```text
[     0.303225s]  INFO(runtime::comms): network addresses: MAC=e8-eb-1b-13-4a-4e IPv4=192.168.1.75 IPv6-LL=fe80::eaeb:1bff:fe13:4a4e IPv6: no configured address
[     0.324758s]  INFO(runtime::comms): diag: before PS-FCLK identifier_read CSR probe
[     0.332332s]  INFO(runtime::comms): diag: PS-FCLK identifier_read returned 9+unknown;13_dio0_dio1_ps_fclk_sys_identifier_probe
[     0.343681s]  INFO(runtime::comms): diag: after PS-FCLK identifier_read CSR probe
[     0.351145s]  INFO(runtime::comms): diag: before rtio_mgt startup
```

It also reached the expected metadata-only RTIO management path:

```text
[     0.357222s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: generated CSR bases identifier=0x80000000 sys_crg=absent rtio_core=0x80000800
[     0.416419s]  INFO(runtime::rtio_mgt): diag: rtio csr preflight: runtime cfg has_sys_crg=false
[     0.467892s]  INFO(runtime::rtio_mgt): diag: skipping SED spread CSR write value 0 after 09 populated-carrier hang
[     0.507385s]  INFO(runtime::rtio_mgt): diag: skipping rtio_core reset_phy CSR write
```

The runtime then started the management/control services and entered the network
poll loop:

```text
[     0.586375s]  INFO(runtime::comms): diag: after mgmt start
[     0.598700s]  INFO(runtime::comms): diag: after control accept task spawn
[     0.605469s]  INFO(runtime::comms): diag: entering network poll loop
[     3.619096s]  INFO(libboard_zynq::eth): eth: got Link { speed: S1000, duplex: Full }
[    19.999962s]  INFO(runtime::comms): diag: network poll heartbeat
```

## Updated Interpretation

This result proves that the populated-carrier boot problem is not a universal
PS-to-PL CSR failure. A real PL CSR transaction, `identifier_read()`, completes
when the diagnostic fabric is clocked from Zynq PS FCLK and the standalone
`sys_crg` block is absent.

That strongly shifts the diagnosis toward the original standalone
SYS_CRG/MMCM/reset/clock-domain integration, or toward CSR transactions that
depend on that generated `sys_crg`/RTIO fabric. It argues against the flake,
SD-card packaging, the basic AXI-to-CSR bridge, and the identifier CSR block as
standalone root causes.

The next useful experiment should not be another broad rebuild. It should
reintroduce the original standalone clocking pieces one at a time, or instrument
the SYS_CRG/RTIO CSR path with a timeout/response diagnostic, so the next boot
answers exactly which part of the original clock/reset fabric makes CSR reads
stop completing.
