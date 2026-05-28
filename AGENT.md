# MADMAX Agent Instructions

## Physical Hardware Safety

The Kasli-SoC is connected to the real experimental node. Do not run commands
that test, probe, stimulate, reset, power-cycle, flash, connect to, or otherwise
interact with physical hardware unless the user explicitly performs the action
or gives a specific instruction for that exact hardware operation.

In particular, do not run `ping`, `nc`, `artiq_coremgmt`, JTAG loaders, serial
control scripts, network scans, power-control scripts, or any experiment code
against the real node on your own initiative. It is OK to build artifacts,
inspect files, read logs provided by the user, and tell the user what manual
test they should run.

When the user asks to build "gateware" for a Kasli-SoC board test, the requested
deliverable is the packaged `boot.bin` file, not just the raw FPGA bitstream.

`top.bit` is only an intermediate build artifact. A gateware build is not done
until the matching firmware has been built and a fresh `boot.bin` has been
packaged from the same gateware description, bitstream, and firmware ELF.

Default handoff artifact:

- `boot.bin`

Also report the path and SHA256 of that `boot.bin`. Mention `top.bit` only as
supporting evidence or when the user explicitly asks for the bitstream.

The older typo file `AGNET.md` contains the detailed build checklist. Follow its
process, but treat this file as the naming-correct agent entrypoint.
