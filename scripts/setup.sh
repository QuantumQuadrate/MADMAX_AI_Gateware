#!/bin/bash

# Setup script for MADMAX-AI-Gateware

echo "Setting up MADMAX-AI-Gateware..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "uv is not installed. Please install uv from https://github.com/astral-sh/uv"
    exit 1
fi

# Install dependencies
echo "Installing Python dependencies..."
uv sync

# Initialize submodules
echo "Initializing submodules..."
./scripts/init_submodules.sh

echo "Setup complete. Run 'madmax setup' to verify."