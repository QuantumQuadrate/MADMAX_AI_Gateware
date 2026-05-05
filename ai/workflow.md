# AI Workflow

The AI pipeline is intentionally narrow at the top and deterministic below it.

1. User request: describe the desired experiment in lab terms.
2. Config edit: update one YAML file in `configs/experiments/`.
3. Validation: run `madmax validate`.
4. Generation: run the settings, device DB, and experiment generators.
5. Test: run `pytest` and inspect generated smoke experiments.
6. Build planning: run `madmax build-gateware --dry-run`.
7. Build execution: only run the real ARTIQ/Kasli-SoC build after the command is reviewed.

Generated files are disposable. The YAML config is the durable experiment intent.

