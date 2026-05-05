# Creating Gateware for Atom-Photon Mode

## Overview

This document describes the process of creating gateware for the atom-photon mode of the MADMAX entangler core.

## Steps Taken

### 1. Update Configuration Schema

- Added `mode` field to the `Entangler` Pydantic model in `madmax_ai_gateware/config.py`
- Updated the JSON schema in `configs/schemas/experiment.schema.json` to include the mode field
- Modified the settings template in `configs/templates/settings.toml.j2` to include the mode

### 2. Create Atom-Photon Mode Configuration

- Created `configs/experiments/atom_photon_mode.yaml` with:
  - Single input (DIO0) and output (DIO1)
  - Mode set to "atom_photon"
  - Optimized timing parameters for photon detection
  - Updated build command template to pass MODE parameter

### 3. Validate and Generate

- Validated the new config using `madmax validate`
- Generated settings.toml with the mode included
- Generated build command with MODE=atom_photon

### 4. Testing

- Ran all existing tests to ensure no regressions
- Verified generation works correctly

## Key Changes

- **Config Model**: Added optional `mode` field with default "default"
- **Schema**: Made mode optional in JSON schema
- **Template**: Added mode to settings.toml output
- **Build Command**: Updated to pass mode as environment variable or parameter

## Usage

To build gateware for atom-photon mode:

```bash
madmax validate --config configs/experiments/atom_photon_mode.yaml
madmax generate-settings --config configs/experiments/atom_photon_mode.yaml
madmax build-gateware --config configs/experiments/atom_photon_mode.yaml
```

## Notes

- The actual gateware compilation requires the madmax-entangler-core submodule to be initialized
- The MODE parameter is passed to the build system for conditional compilation
- This configuration is optimized for single-photon detection and atom state readout