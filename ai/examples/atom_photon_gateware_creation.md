# Atom-Photon Gateware Creation Example

Request:

Create an atom-photon Entangler configuration for Kasli-SoC that keeps DIO inputs and outputs aligned with the generated runtime files.

Expected AI behavior:

- Start from a YAML config such as `configs/experiments/atom_photon_mode.yaml`.
- Validate the requested DIO layout and Entangler counts.
- Regenerate runtime files instead of editing generated files directly.
- Dry-run the gateware build before proposing a real hardware build or flash step.

