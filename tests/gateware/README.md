# Gateware Tests

This folder is for tests that protect the gateware build contract.

Use it for checks that a newly made gateware mode:

- points at the intended JSON description in `gateware_build/descriptions/`;
- records the selected entangler-core branch in its experiment config;
- renders a dry-run build command using the same JSON description that will be built;
- keeps the software bypass contract for TTL-owning custom logic.
