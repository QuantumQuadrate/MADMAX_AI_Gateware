#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-gateware_build/configs/experiments/2in_2out.yaml}"
uv run madmax build-gateware --config "$CONFIG" --dry-run

