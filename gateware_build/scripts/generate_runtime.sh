#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-gateware_build/configs/experiments/2in_2out.yaml}"
uv run madmax validate --config "$CONFIG"
uv run madmax generate-settings --config "$CONFIG"
uv run madmax generate-device-db --config "$CONFIG"
uv run madmax generate-experiment --config "$CONFIG"
uv run madmax generate-artiq-json --config "$CONFIG"
