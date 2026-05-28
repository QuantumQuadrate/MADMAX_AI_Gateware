# Gateware Build Checklist

This file is the required checklist for every MADMAX Kasli-SoC gateware build.
Follow it in order. A gateware build is not complete until a matching `boot.bin`
has been packaged and the generated runtime files are consistent with the same
source configuration.

## 1. Start From A Clean Build Intention

- Identify the source experiment YAML, usually `configs/experiments/2in_2out.yaml`.
- Confirm the target board is `kasli_soc`.
- Confirm the intended RTIO role:
  - `standalone` and `master` use `runtime`.
  - `satellite` uses `satman`.
- Do not reuse an old `top.bit`, firmware ELF/bin, JSON description, or
  `entangler_settings.toml` unless it was generated from the exact same source
  configuration.

## 2. Initialize The Workspace

Run these from the repository root:

```bash
uv sync
git submodule update --init --recursive
uv run madmax setup
```

The build depends on these submodules being present:

- `repos/madmax-artiq-env`
- `repos/madmax-artiq-zynq`
- `repos/madmax-entangler-core`

## 3. Validate The Experiment Config

```bash
export CONFIG=configs/experiments/2in_2out.yaml
uv run madmax validate --config "$CONFIG" --require-submodules
```

Fix validation errors before continuing. The validator checks pad names,
Entangler input/output counts, duplicated pads, and required repository paths.

## 4. Generate All Runtime And Build Inputs

```bash
./scripts/generate_runtime.sh "$CONFIG"
```

This must produce:

- `build/generated/settings.toml`
- `build/generated/entangler_settings.toml`
- `build/generated/<variant>.json`
- `build/generated/device_db.py`
- `build/generated/experiments/*_smoke.py`

Before building, inspect the generated ARTIQ description and Entangler settings:

```bash
sed -n '1,160p' build/generated/*.json
sed -n '1,160p' build/generated/entangler_settings.toml
```

The JSON and `entangler_settings.toml` must agree with the intended channel
counts and EEM port.

## 5. Confirm The Build Command

```bash
uv run madmax build-gateware --config "$CONFIG" --dry-run
```

The command must reference:

- `build/generated/<variant>.json`
- `build/generated/entangler_settings.toml`
- `repos/madmax-artiq-zynq/src/gateware/kasli_soc.py`

The generated Entangler settings must be copied into
`repos/madmax-artiq-zynq/entangler_settings.toml` before invoking Nix.

## 6. Build The Raw Gateware

The wrapper command builds the raw bitstream:

```bash
uv run madmax build-gateware --config "$CONFIG"
```

Expected output:

- `build/generated/gateware/top.bit`

`top.bit` alone is not a deployable Kasli-SoC SD-card image.

## 7. Build Matching Firmware

Use the same generated JSON description that produced `top.bit`.

```bash
export DESC="$PWD/build/generated/entangler_1dio_2in_2out.json"
export ROLE=standalone

case "$ROLE" in
  standalone|master) export FIRMWARE=runtime ;;
  satellite) export FIRMWARE=satman ;;
  *) echo "Invalid ROLE: $ROLE" >&2; exit 1 ;;
esac

cd repos/madmax-artiq-zynq/src
nix develop --command make TARGET=kasli_soc GWARGS="$DESC" "$FIRMWARE"
cd -
```

Expected output in `repos/madmax-artiq-zynq/build/`:

- `runtime.bin` and `firmware/armv7-none-eabihf/release/runtime`, or
- `satman.bin` and `firmware/armv7-none-eabihf/release/satman`

The firmware must be rebuilt whenever the gateware JSON changes. Mismatched
firmware and gateware can stop boot before the network address is printed.

## 8. Package `boot.bin`

Build or fetch the Kasli-SoC second-stage bootloader:

```bash
cd repos/madmax-artiq-zynq
mkdir -p build
cd build
nix build git+https://git.m-labs.hk/m-labs/zynq-rs#kasli_soc-szl
cd ..
```

Copy or link the newly built `top.bit` into the same build tree if needed:

```bash
mkdir -p build/gateware
cp ../../build/generated/gateware/top.bit build/gateware/top.bit
```

Create the boot image:

```bash
cd build
printf '%s\n' \
  'the_ROM_image:' \
  '{' \
  '  [bootloader]result/szl.elf' \
  '  gateware/top.bit' \
  "  firmware/armv7-none-eabihf/release/$FIRMWARE" \
  '}' > boot.bif

nix develop .. --command mkbootimage boot.bif boot.bin
cd -
```

Expected final artifact:

- `repos/madmax-artiq-zynq/build/boot.bin`

This is the file to copy to the SD card as `BOOT.BIN` or install through
`artiq_coremgmt config write -f boot`.

## 9. Verify Runtime Configuration

Use the generated `device_db.py` that came from the same source config:

```bash
sed -n '1,220p' build/generated/device_db.py
```

Confirm:

- `core` host matches the board IP.
- TTL channel mapping matches the generated gateware.
- Entangler device names and counts match the generated Entangler settings.

If the SD card uses `config.txt`, confirm network and clock keys:

```text
ip=<board IPv4 address>
mac=<board MAC address>
rtio_clock=int_125
```

Only use a different `rtio_clock` when the hardware clock source is physically
present and intended.

## 10. Boot And Check UART

After flashing or copying `boot.bin`, watch UART at `115200 8-N-1`.

The boot should progress through:

- `NAR3/Zynq7000 starting...`
- `gateware ident: ...`
- RTIO clock setup messages
- `network addresses: ...`

If boot stops before `network addresses: ...`, investigate gateware/firmware
matching, RTIO clock setup, and PLL/SYS clock switching before debugging IP
assignment.

## 11. Never Skip These Rules

- Always generate JSON, Entangler settings, firmware, and `boot.bin` from the
  same config.
- Always rebuild firmware after changing the gateware description.
- Always package a fresh `boot.bin`; do not deploy `top.bit` by itself.
- Always keep the generated device DB with the same build that produced the
  boot image.
- Always capture the UART log for failed boots.
