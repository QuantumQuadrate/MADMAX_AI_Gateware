#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-configs/experiments/2in_2out.yaml}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install uv first, then run this script again." >&2
  exit 1
fi

exec uv run madmax web-gui --config "$CONFIG"

