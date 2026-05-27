# Node 1 Standalone Boot Findings

Date: 2026-05-26

## Goal

Build a native, non-entangler Kasli-SoC Node 1 standalone image for the crate
with all Node 1 cards installed, so the board reaches runtime networking and can
be pinged at the normal Node 1 address.

## Findings

- The remembered Node 1 JSON is:
  `repos/qn_artiq_routines/kasli-soc-standalone_node1_with_edgecounters_en.json`.
- The copy in `repos/madmax-artiq-zynq/` is byte-identical:
  `repos/madmax-artiq-zynq/kasli-soc-standalone_node1_with_edgecounters_en.json`.
- This JSON is the full Node 1 crate layout, not the smaller atom-photon test
  Kasli layout:
  - DIO on EEM0 with edge counters.
  - DIO on EEM1 with edge counters.
  - Sampler cards on EEM2, EEM3, and EEM4.
  - Zotino on EEM5.
  - Urukul cards on EEM6/EEM7, EEM8/EEM9, and EEM10/EEM11.
- The JSON has no `entangler` peripheral. With the current `kasli_soc.py`
  conditional injection, this build uses the native ARTIQ DIO path and does not
  monkey-patch the DIO builder.
- Dry layout generation succeeds and reports:
  - DIO EEM0 at RTIO `0x000000`.
  - DIO EEM1 at RTIO `0x00000c`.
  - Samplers at RTIO `0x000018`, `0x00001b`, and `0x00001e`.
  - Zotino at RTIO `0x000021`.
  - Urukuls at RTIO `0x000024`, `0x00002b`, and `0x000032`.
  - User LEDs at RTIO `0x000039` and `0x00003a`.
- The earlier atom-photon boot log reached `runtime` and printed a gateware
  ident, so that image was no longer failing before the ident read. Its
  remaining `device_map` line was a non-fatal warning about RTIO error-message
  names.
- Network address selection is not encoded in `top.bit` or the JSON gateware
  description. ARTIQ-Zynq reads it from the board configuration, usually
  `config.txt` on the SD card or the persistent config storage. The Node 1 QN
  device DB files use `192.168.1.75`, while the generated `madmax-artiq-zynq`
  device DB default was `192.168.1.70`.

## Build Command

The full boot image is built from the native Node 1 JSON with:

```bash
./gateware_build/scripts/build_from_json.sh \
  repos/madmax-artiq-zynq/kasli-soc-standalone_node1_with_edgecounters_en.json \
  standalone
```

Expected primary artifact:

```text
repos/madmax-artiq-zynq/build/boot.bin
```

Build result:

- `repos/madmax-artiq-zynq/build/boot.bin` was generated successfully.
- `repos/madmax-artiq-zynq/build/gateware/top.bit` was generated successfully.
- `repos/madmax-artiq-zynq/build/runtime.bin` was generated successfully.
- Vivado route timing passed with `WNS = 0.348 ns`, `TNS = 0`, and
  `All user specified timing constraints are met`.
- Route status reports `0` routing errors and all `29549` routable nets fully
  routed.
- DRC reports `30` warnings and `0` errors. The warnings are the usual
  bidirectional/input-buffer LVDS warnings for the ARTIQ EEM-style interfaces.

Packaged copy:

```text
gateware_build/artifacts/node1_standalone_20260526/
```

This directory contains:

- `boot.bin`: SD-card boot image.
- `config.txt`: root-level SD-card network/clock config for Node 1.
- `config/device_map.bin`: config-folder device map for RTIO error-message
  names.
- `device_db.py`: matching generated ARTIQ device DB, patched to
  `core_addr = "192.168.1.75"`.
- `kasli-soc-standalone_node1_with_edgecounters_en.json`: JSON used for the
  build.
- `SHA256SUMS`: checksums for `boot.bin` and `device_map.bin`.

Checksums:

```text
554528c00d2d8a53eac8e112893bd09431365625563718cd98f59cd3eb25f923  boot.bin
163f710c3ab0a125010ebdbc86a4012f6224986d783a328a764cf7d267d95177  device_map.bin
```

## SD-Card Network Configuration

To force the normal Node 1 address when copying `boot.bin` directly to the SD
card, put this `config.txt` at the root of the FAT partition:

```text
ip=192.168.1.75
rtio_clock=int_125
```

Also put `device_map.bin` at:

```text
config/device_map.bin
```

If the board already has persistent config storage with the right address,
`config.txt` is not required. It is useful when a test-card SD card or stale
config is being reused.

## Hardware Note

The gateware JSON describes the RTIO layout and FPGA interfaces. The Kasli-SoC
runtime does not probe every Sampler/Zotino/Urukul at network bring-up. Those
cards are normally touched later by ARTIQ drivers and experiments. A hang before
networking is therefore more likely to come from the wrong bitstream/runtime
pair, a bad DIO/global gateware patch, or board config/clocking than from an
absent Sampler/Zotino/Urukul.

## Incremental Card-List Builds

For the second diagnostic path, generate cumulative native JSON descriptions
from the original Node 1 JSON:

```bash
./gateware_build/scripts/generate_node1_incremental_jsons.py
```

The generated files live in:

```text
gateware_build/descriptions/node1_incremental/
```

Build commands are written to:

```text
gateware_build/descriptions/node1_incremental/BUILD_COMMANDS.md
```

To build and package a single cumulative variant:

```bash
./gateware_build/scripts/generate_node1_incremental_jsons.py --build --only 3
```

Packaged incremental results are written under:

```text
gateware_build/artifacts/node1_incremental/
```

The sequence is:

- EEM0 DIO only.
- EEM0 DIO plus EEM1 DIO.
- Add Samplers on EEM2, EEM3, then EEM4.
- Add Zotino on EEM5.
- Add Urukuls on EEM6/EEM7, EEM8/EEM9, then EEM10/EEM11.

Each generated JSON is native/non-entangler. This isolates card-list effects
from the atom-photon entangler overlay and custom entangler PHY/core logic.

## Network-Safe Bring-Up Image

A second diagnostic image was created after the normal Node 1 image. It uses the
same verified full Node 1 `top.bit`, but the runtime intentionally skips
`rtio_clocking::init()` for standalone Kasli-SoC so that it does not touch the
Si5324 or perform the SYS/RTIO clock switch before Ethernet startup.

Packaged copy:

```text
gateware_build/artifacts/node1_standalone_network_safe_20260526/
```

Boot this image first if the board does not reach the network with the normal
image. A successful boot should include this UART line before network setup:

```text
Node 1 network bring-up build: leaving SYS/RTIO on bootstrap clock and skipping RTIO clock switch
```

Interpretation:

- If this image reaches `runtime::comms: network addresses` and is pingable, the
  previous hang is in RTIO clock setup/switching, not in the JSON card list.
- If this image still hangs before `network addresses`, the remaining suspects
  are before RTIO clocking: gateware ident read, I2C/PCA9548/io-expander init,
  or basic runtime/platform mismatch.

This image is for network bring-up and diagnosis. RTIO timing is not expected to
be experiment-ready because the normal RTIO clock switch is skipped.

Checksums:

```text
3c299f3894a282a10e74d0c8b800fa1885d5831da442c41f865e836ae25103aa  boot.bin
163f710c3ab0a125010ebdbc86a4012f6224986d783a328a764cf7d267d95177  device_map.bin
```
