#!/usr/bin/env bash
set -euo pipefail

DESC="${1:?Usage: gateware_build/scripts/build_from_json.sh <description.json> [standalone|master|satellite] [entangler_settings.toml] [entangler-core-branch]}"
ROLE="${2:-standalone}"
SETTINGS="${3:-}"
CORE_BRANCH="${4:-}"

case "$ROLE" in
  standalone|master)
    FIRMWARE="runtime"
    ;;
  satellite)
    FIRMWARE="satman"
    ;;
  *)
    echo "ROLE must be standalone, master, or satellite" >&2
    exit 1
    ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DESC_ABS="$(realpath "$DESC")"
ZYNQ="$ROOT/repos/madmax-artiq-zynq"
ENTANGLER_CORE="$ROOT/repos/madmax-entangler-core"
NIX_ARGS=()

if [[ ! -f "$DESC_ABS" ]]; then
  echo "Description JSON does not exist: $DESC_ABS" >&2
  exit 1
fi

USES_ENTANGLER="$(
  python3 - "$DESC_ABS" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as description_file:
    description = json.load(description_file)

print("yes" if any(
    peripheral.get("type") == "entangler"
    for peripheral in description.get("peripherals", [])
) else "no")
PY
)"

if [[ "$USES_ENTANGLER" == "yes" ]]; then
  NIX_ARGS=(--override-input entangler-core "path:$ENTANGLER_CORE")
fi

if [[ -n "$SETTINGS" && "$USES_ENTANGLER" == "yes" ]]; then
  SETTINGS_ABS="$(realpath "$SETTINGS")"
  if [[ ! -f "$SETTINGS_ABS" ]]; then
    echo "Entangler settings file does not exist: $SETTINGS_ABS" >&2
    exit 1
  fi
  cp "$SETTINGS_ABS" "$ZYNQ/entangler_settings.toml"
  echo "Updated $ZYNQ/entangler_settings.toml from $SETTINGS_ABS"
elif [[ -n "$SETTINGS" ]]; then
  echo "Ignoring entangler settings for native non-entangler JSON: $SETTINGS"
fi

if [[ -n "$CORE_BRANCH" && "$USES_ENTANGLER" == "yes" ]]; then
  if [[ -n "$(git -C "$ENTANGLER_CORE" status --short)" ]]; then
    echo "madmax-entangler-core has uncommitted changes; refusing to switch branches" >&2
    exit 1
  fi
  if git -C "$ENTANGLER_CORE" show-ref --verify --quiet "refs/heads/$CORE_BRANCH"; then
    git -C "$ENTANGLER_CORE" checkout "$CORE_BRANCH"
  elif git -C "$ENTANGLER_CORE" show-ref --verify --quiet "refs/remotes/origin/$CORE_BRANCH"; then
    git -C "$ENTANGLER_CORE" checkout -B "$CORE_BRANCH" "origin/$CORE_BRANCH"
  else
    echo "Unknown entangler-core branch: $CORE_BRANCH" >&2
    exit 1
  fi
elif [[ -n "$CORE_BRANCH" ]]; then
  echo "Ignoring entangler-core branch for native non-entangler JSON: $CORE_BRANCH"
fi

if [[ "$USES_ENTANGLER" == "yes" ]]; then
  echo "Using entangler core checkout: $(git -C "$ENTANGLER_CORE" branch --show-current) ($(git -C "$ENTANGLER_CORE" rev-parse --short HEAD))"
else
  echo "Native non-entangler JSON: using the regular ARTIQ peripheral path"
fi

cd "$ZYNQ"
nix develop "${NIX_ARGS[@]}" --command bash -lc 'cd src && python gateware/kasli_soc.py -g ../build/gateware "$1"' bash "$DESC_ABS"
nix develop "${NIX_ARGS[@]}" --command bash -lc 'cd src && make TARGET=kasli_soc GWARGS="$1" "$2"' bash "$DESC_ABS" "$FIRMWARE"

mkdir -p "$ZYNQ/build"
cd "$ZYNQ/build"
nix build git+https://git.m-labs.hk/m-labs/zynq-rs#kasli_soc-szl

printf '%s\n' \
  'the_ROM_image:' \
  '{' \
  '  [bootloader]result/szl.elf' \
  '  gateware/top.bit' \
  "  firmware/armv7-none-eabihf/release/$FIRMWARE" \
  '}' > boot.bif

nix develop "${NIX_ARGS[@]}" .. --command mkbootimage boot.bif boot.bin

cd "$ZYNQ"
nix develop "${NIX_ARGS[@]}" --command bash -lc 'python entangler_device_db_maker.py "$1" > device_db.py' bash "$DESC_ABS"

echo "Build complete:"
echo "  $ZYNQ/build/boot.bin"
echo "  $ZYNQ/device_db.py"
