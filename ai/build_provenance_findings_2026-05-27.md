# Kasli-SoC Build Provenance Findings

Date: 2026-05-27

## Executive Summary

The populated Kasli-SoC crate is not the root failure by itself. The decisive
new observation is that a separate known-good `boot.bin` boots the same
populated system correctly. That means the active fault is in the image we are
building or packaging: JSON inputs, gateware defaults, firmware/gateware CSR
pairing, runtime diagnostics, or `boot.bin` assembly.

The highest-confidence build-flow issue found so far is stale CSR provenance:
firmware can be built from `pl.rs`, `rustc-cfg`, and `mem.rs` that were not
regenerated with the bitstream being packaged.

## Why This Is Not A Hardware-Only Finding

The hardware claim changed because of this user-provided fact:

- A different `boot.bin` works correctly on the populated system.

Therefore:

- The populated cards/carrier cannot be treated as simply bad hardware.
- The populated-system failure of our generated images must be explained by
  something different between the known-good image and our generated image.
- Any diagnostic path that assumes the hardware population alone is the cause is
  now lower priority than build-output comparison.

## Concrete Evidence In This Workspace

Observed artifact timestamps:

```text
2026-05-27 08:12 repos/madmax-artiq-zynq/build/pl.rs
2026-05-27 08:12 repos/madmax-artiq-zynq/build/rustc-cfg
2026-05-27 08:12 repos/madmax-artiq-zynq/build/mem.rs
2026-05-27 11:22 repos/madmax-artiq-zynq/build/gateware/top.bit
2026-05-27 12:51 repos/madmax-artiq-zynq/build/runtime.bin
```

This is a bad provenance shape. `runtime.bin` is compiled against Rust CSR and
memory-map files, while `boot.bin` packages a bitstream that must expose the
same CSR map. If `top.bit` and `pl.rs`/`mem.rs` come from different gateware
generations, early runtime CSR reads and writes can hang or target the wrong
registers.

The exact stale files seen were:

```text
repos/madmax-artiq-zynq/build/pl.rs
repos/madmax-artiq-zynq/build/rustc-cfg
repos/madmax-artiq-zynq/build/mem.rs
```

## Build-System Root Cause

`repos/madmax-artiq-zynq/src/Makefile` generated CSR metadata from:

```make
../build/pl.rs ../build/rustc-cfg ../build/mem.rs: gateware/*
```

That dependency list did not include the JSON system description passed through
`GWARGS`. As a result, `make TARGET=kasli_soc GWARGS=<desc.json> runtime` could
reuse old CSR metadata even when the JSON or bitstream had changed.

This is especially dangerous for the Node 1/full-crate workflow because the JSON
description controls EEM peripherals, RTIO channels, CSR devices, and generated
firmware configuration.

## Other Build Mismatches To Keep In View

These are not proven root causes yet, but they are now comparison targets
against the known-good image:

- The full Node 1 JSON at
  `repos/madmax-artiq-zynq/kasli-soc-standalone_node1_with_edgecounters_en.json`
  uses `"base": "standalone"`.
- The generated incremental JSONs use `"drtio_role": "standalone"`.
- Generated JSONs include explicit defaults such as `"enable_wrpll": false` and
  `"sed_lanes": 8`, while the known full JSON leaves those unspecified.
- Generated JSONs hardcode `"hw_rev": "v1.0"`. If the known-good populated image
  used a different Kasli-SoC hardware revision or runtime config path, that must
  be compared.

## Fixes Added

The local build flow now has two guardrails:

1. `repos/madmax-artiq-zynq/src/Makefile` forces regeneration of `pl.rs`,
   `rustc-cfg`, and `mem.rs` before firmware builds.
2. `scripts/build_from_json.sh` performs the whole deployable-image flow:
   build `top.bit`, delete stale CSR metadata, build matching firmware, build
   the Kasli-SoC SZL, package `boot.bin`, and write a hash manifest.

The example YAML `build.command_template` values now call
`scripts/build_from_json.sh` instead of stopping after raw bitstream generation.

## Production Caution

The current `repos/madmax-artiq-zynq` working tree still contains diagnostic
runtime edits in these files:

```text
src/runtime/src/main.rs
src/runtime/src/comms.rs
src/runtime/src/rtio_clocking.rs
src/runtime/src/rtio_mgt.rs
```

A fresh `boot.bin` built from the current tree would now have better artifact
provenance, but it would still include diagnostic runtime behavior unless those
runtime patches are intentionally kept or reverted.

## Verification Performed

After adding the build-flow guardrails:

```text
uv run pytest
10 passed
```

```text
bash -n scripts/build_from_json.sh
passed
```

```text
git diff --check
passed
```

The dry-run command now resolves to:

```text
scripts/build_from_json.sh <generated-json> standalone <artifact-dir>
```

## Next Build To Trust

The next trustworthy production test should be built from a clean or explicitly
chosen runtime tree using:

```bash
scripts/build_from_json.sh \
  repos/madmax-artiq-zynq/kasli-soc-standalone_node1_with_edgecounters_en.json \
  standalone \
  build/artifacts/node1_standalone_matched_20260527
```

Before flashing that image, inspect the generated `build-manifest.txt` and
confirm that `top.bit`, firmware, CSR metadata, and `boot.bin` were produced in
the same run.
