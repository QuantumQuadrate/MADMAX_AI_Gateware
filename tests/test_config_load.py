import pytest
import pathlib
from madmax_ai_gateware.validate import load_config, validate_config
from madmax_ai_gateware.config import Config
from madmax_ai_gateware.paths import CONFIGS_DIR

def test_load_example_config():
    config_path = CONFIGS_DIR / "experiments" / "2in_2out.yaml"
    config = load_config(config_path)
    assert isinstance(config, Config)
    assert config.experiment.name == "2in_2out"
    assert config.entangler.num_inputs == 2
    assert config.entangler.num_outputs == 2

def test_validate_example_config():
    config_path = CONFIGS_DIR / "experiments" / "2in_2out.yaml"
    config = load_config(config_path)
    errors = validate_config(config)
    assert len(errors) == 0