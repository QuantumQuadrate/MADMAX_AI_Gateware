# Example AI Request: 2 Input 2 Output Entangler

User Request: "I want to test a simple 2-input 2-output entangler with fast branching for low-latency decisions. Use DIO0-DIO3 on EEM0."

AI Response:
- Modify `configs/experiments/2in_2out.yaml` to match the request.
- Set num_inputs: 2, num_outputs: 2, fast_branch: true.
- Set input_pads: ["DIO0", "DIO1"], output_pads: ["DIO2", "DIO3"].
- Validate the config.
- Generate files.
- Build gateware.
- Generate test experiment that toggles outputs based on inputs.