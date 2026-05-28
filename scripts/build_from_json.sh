#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 DESC ROLE [ARCHIVE_DIR]" >&2
    echo "  DESC: Kasli-SoC JSON description path" >&2
    echo "  ROLE: standalone, master, or satellite" >&2
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
    usage
    exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESC_INPUT="$1"
ROLE="$2"
ARCHIVE_DIR="${3:-}"

if [[ "$DESC_INPUT" = /* ]]; then
    DESC="$DESC_INPUT"
else
    DESC="$ROOT/$DESC_INPUT"
fi
DESC="$(realpath "$DESC")"

if [[ ! -f "$DESC" ]]; then
    echo "description JSON not found: $DESC" >&2
    exit 1
fi

case "$ROLE" in
    standalone|master)
        FIRMWARE=runtime
        ;;
    satellite)
        FIRMWARE=satman
        ;;
    *)
        usage
        exit 2
        ;;
esac

ZYNQ_DIR="$ROOT/repos/madmax-artiq-zynq"
BUILD_DIR="$ZYNQ_DIR/build"

mkdir -p "$BUILD_DIR"

echo "Building gateware from $DESC"
(
    cd "$ZYNQ_DIR/src"
    nix develop .. --command python gateware/kasli_soc.py -g ../build/gateware "$DESC"
)

echo "Building matching $FIRMWARE firmware"
rm -f "$BUILD_DIR/pl.rs" "$BUILD_DIR/rustc-cfg" "$BUILD_DIR/mem.rs"
(
    cd "$ZYNQ_DIR/src"
    nix develop .. --command make TARGET=kasli_soc GWARGS="$DESC" "$FIRMWARE"
)

echo "Building Kasli-SoC second-stage loader"
(
    cd "$BUILD_DIR"
    nix build git+https://git.m-labs.hk/m-labs/zynq-rs#kasli_soc-szl
)

echo "Packaging boot.bin"
cat > "$BUILD_DIR/boot.bif" <<EOF
the_ROM_image:
{
  [bootloader]result/szl.elf
  gateware/top.bit
  firmware/armv7-none-eabihf/release/$FIRMWARE
}
EOF
(
    cd "$BUILD_DIR"
    nix develop "$ZYNQ_DIR" --command mkbootimage boot.bif boot.bin
)

MANIFEST="$BUILD_DIR/build-manifest.txt"
{
    echo "date: $(date -Iseconds)"
    echo "description: $DESC"
    echo "role: $ROLE"
    echo "firmware: $FIRMWARE"
    echo
    sha256sum "$DESC" \
        "$BUILD_DIR/gateware/top.bit" \
        "$BUILD_DIR/firmware/armv7-none-eabihf/release/$FIRMWARE" \
        "$BUILD_DIR/$FIRMWARE.bin" \
        "$BUILD_DIR/boot.bin" \
        "$BUILD_DIR/pl.rs" \
        "$BUILD_DIR/rustc-cfg" \
        "$BUILD_DIR/mem.rs"
} > "$MANIFEST"

if [[ -n "$ARCHIVE_DIR" ]]; then
    if [[ "$ARCHIVE_DIR" != /* ]]; then
        ARCHIVE_DIR="$ROOT/$ARCHIVE_DIR"
    fi
    mkdir -p "$ARCHIVE_DIR"
    cp "$BUILD_DIR/boot.bin" "$ARCHIVE_DIR/boot.bin"
    cp "$BUILD_DIR/$FIRMWARE.bin" "$ARCHIVE_DIR/$FIRMWARE.bin"
    cp "$BUILD_DIR/firmware/armv7-none-eabihf/release/$FIRMWARE" "$ARCHIVE_DIR/$FIRMWARE.elf"
    cp "$BUILD_DIR/gateware/top.bit" "$ARCHIVE_DIR/top.bit"
    cp "$BUILD_DIR/boot.bif" "$ARCHIVE_DIR/boot.bif"
    cp "$BUILD_DIR/pl.rs" "$ARCHIVE_DIR/pl.rs"
    cp "$BUILD_DIR/rustc-cfg" "$ARCHIVE_DIR/rustc-cfg"
    cp "$BUILD_DIR/mem.rs" "$ARCHIVE_DIR/mem.rs"
    cp "$MANIFEST" "$ARCHIVE_DIR/build-manifest.txt"
    echo "Archived matched artifacts in $ARCHIVE_DIR"
fi

echo "Done: $BUILD_DIR/boot.bin"
echo "Manifest: $MANIFEST"
