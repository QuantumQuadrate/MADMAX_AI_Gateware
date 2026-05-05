#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-configs/experiments/2in_2out.yaml}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install uv first, then run this script again." >&2
  exit 1
fi

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo "No desktop display was detected. Start this from an X11 or Wayland desktop session." >&2
  exit 1
fi

uv sync --extra gui
exec uv run --extra gui madmax gui --config "$CONFIG"

