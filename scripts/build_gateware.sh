#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-configs/experiments/2in_2out.yaml}"
uv run madmax build-gateware --config "$CONFIG" --dry-run

