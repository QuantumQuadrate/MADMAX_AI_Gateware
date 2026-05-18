from madmax_ai_gateware.config import load_config
from madmax_ai_gateware.paths import DEFAULT_CONFIG
from madmax_ai_gateware.validate import validate_config


def test_validation_passes_for_2in_2out():
    cfg = load_config(DEFAULT_CONFIG)

    assert validate_config(cfg) == []
    assert cfg.entangler.num_inputs == 2
    assert cfg.entangler.num_outputs == 2
    assert cfg.hardware.input_pads == ["dio0", "dio1"]
    assert cfg.hardware.output_pads == ["dio2", "dio3"]


def test_validation_requires_software_ttl_bypass():
    cfg = load_config(DEFAULT_CONFIG)
    cfg.entangler.ttl_bypass.required = False

    assert "entangler.ttl_bypass.required must stay true" in validate_config(cfg)[0]
