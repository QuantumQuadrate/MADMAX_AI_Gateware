# AI Workflow for MADMAX-AI-Gateware

## Overview

The AI workflow integrates human intent with automated gateware development. The process ensures consistency and reproducibility.

## Steps

1. **Intent Capture**: User provides natural language description of desired experiment.

2. **Config Modification**: AI updates the YAML config file based on the description.

3. **Validation**: Run validation to ensure config is correct.

4. **Generation**: Use scripts to generate settings, device_db, and test experiments.

5. **Build**: Build gateware using the configured command.

6. **Test**: Run generated test experiments.

7. **Deploy**: Suggest flashing and running real experiments.

## Best Practices

- Always start with the example config and modify it.
- Use dry-run for builds initially.
- Keep a record of changes for reproducibility.
- Test small changes incrementally.