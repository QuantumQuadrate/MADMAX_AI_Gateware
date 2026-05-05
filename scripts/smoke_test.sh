#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-configs/experiments/2in_2out.yaml}"
uv run pytest
uv run madmax validate --config "$CONFIG"
uv run madmax generate-settings --config "$CONFIG"
uv run madmax generate-device-db --config "$CONFIG"
uv run madmax generate-experiment --config "$CONFIG"
uv run madmax build-gateware --config "$CONFIG" --dry-run

