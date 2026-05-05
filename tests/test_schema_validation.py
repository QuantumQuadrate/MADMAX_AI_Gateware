import pytest
import json
from madmax_ai_gateware.validate import validate_with_schema
from madmax_ai_gateware.paths import CONFIGS_DIR

def test_schema_validation():
    config_path = CONFIGS_DIR / "experiments" / "2in_2out.yaml"
    errors = validate_with_schema(config_path)
    assert len(errors) == 0