# Custom Entangler Logic Request: test custom logic

Create custom entangler logic named `test_custom_logic`.

Base branch: `artiq-integration`
Target branch: `feature/test-custom-logic`

## Description

I want to have 2 tll of the DIO card to input and make an AND and a NAND gate and then output the results on the 2 TTL of the entangler core. I want the other 2 output TTL of the DIO card to be normal output and generate a 2 bit timer like output, and the the other 2 input will take the output and time stamps them and find out the difference between when the timer has generated the pulse and the time that the TTL has a rising or falling edge.

## Required Behavior

TODO: define the gateware behavior.

## Inputs

TODO: define 2 inputs.

## Outputs

TODO: define 2 outputs.

## Success And Failure Rules

TODO: define success, retry, timeout, and failure behavior.

## Test Experiment Behavior

TODO: define smoke, loopback, timing-scan, stress, and benchmark expectations.

## Implementation Expectations

- Work in `repos/madmax-entangler-core` on branch `feature/test-custom-logic`.
- Keep the legacy entangler core stable unless the requested behavior is truly reusable.
- Passthrough is required for every custom design: when the mode is disabled (`enable = 0`), DIO channels owned by the custom logic must behave like normal ARTIQ TTL inputs/outputs wherever physically possible.
- If any owned DIO channel cannot be passed through, document it in the gateware design, JSON/card options, runtime driver, and tests.
- Prefer isolated files for this mode:
  - `entangler/test_custom_logic_core.py`
  - `entangler/test_custom_logic_phy.py`
  - `entangler/test_custom_logic_driver.py`
  - `entangler/test_custom_logic_registers.py`
- Add Migen/Python tests under `repos/madmax-entangler-core/test/`.
- Keep `repos/madmax-artiq-zynq/flake.nix` pointed at the selected entangler-core branch or local path.
- Keep runtime files in `repos/madmax-artiq-env/test_custom_logic/`.
- Keep the generated experiment config in `gateware_build/configs/experiments/test_custom_logic.yaml`.
- Run the verification ladder before suggesting a real gateware build or hardware flashing.
