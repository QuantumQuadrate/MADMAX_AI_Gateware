import yaml
import json
import pathlib
from .config import Config
from .paths import CONFIGS_DIR

def load_config(config_path: pathlib.Path) -> Config:
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)
    return Config(**data)

def validate_config(config: Config) -> List[str]:
    errors = []
    if config.entangler.num_inputs != len(config.hardware.input_pads):
        errors.append(f"num_inputs ({config.entangler.num_inputs}) does not match input_pads count ({len(config.hardware.input_pads)})")
    if config.entangler.num_outputs != len(config.hardware.output_pads):
        errors.append(f"num_outputs ({config.entangler.num_outputs}) does not match output_pads count ({len(config.hardware.output_pads)})")
    # Add more validations as needed
    return errors

def validate_with_schema(config_path: pathlib.Path) -> List[str]:
    schema_path = CONFIGS_DIR / "schemas" / "experiment.schema.json"
    with open(schema_path, 'r') as f:
        schema = json.load(f)
    # For now, just check if it loads
    try:
        config = load_config(config_path)
        return validate_config(config)
    except Exception as e:
        return [str(e)]