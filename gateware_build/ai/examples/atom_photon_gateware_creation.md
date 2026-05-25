# Atom-Photon Gateware Creation Example

Request:

Create an atom-photon Entangler configuration for Kasli-SoC that keeps DIO inputs and outputs aligned with the generated runtime files.

Expected AI behavior:

- Start from a YAML config such as `gateware_build/configs/experiments/atom_photon_mode.yaml`.
- Validate the requested DIO layout and Entangler counts.
- Require disabled-mode passthrough: when custom logic is disabled (`enable = 0`), owned DIO channels must behave like normal ARTIQ TTLs wherever physically possible.
- Regenerate runtime files instead of editing generated files directly.
- Dry-run the gateware build before proposing a real hardware build or flash step.
