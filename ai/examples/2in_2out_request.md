# Example Request

Configure a Kasli-SoC Entangler experiment with two DIO inputs and two DIO outputs on EEM 0. The first two DIO channels should be inputs, the next two should be outputs, and the design should prioritize low-latency branch decisions. Any custom logic must include disabled-mode passthrough so owned DIO channels behave like normal ARTIQ TTLs when `enable = 0`.

Expected AI behavior:

- Update or select `configs/experiments/2in_2out.yaml`.
- Validate the config.
- Generate `settings.toml`, `device_db.py`, and an ARTIQ smoke test.
- Dry-run the gateware build command.
