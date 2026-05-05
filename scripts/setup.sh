#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install it first: https://github.com/astral-sh/uv"
  exit 1
fi

uv sync
uv run madmax setup

