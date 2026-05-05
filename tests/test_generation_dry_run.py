import pytest
import pathlib
import tempfile
from madmax_ai_gateware.validate import load_config
from madmax_ai_gateware.generate_settings import generate_settings
from madmax_ai_gateware.generate_device_db import generate_device_db
from madmax_ai_gateware.build_gateware import build_gateware
from madmax_ai_gateware.paths import CONFIGS_DIR

def test_generate_settings():
    config_path = CONFIGS_DIR / "experiments" / "2in_2out.yaml"
    config = load_config(config_path)
    with tempfile.TemporaryDirectory() as tmp:
        output_path = pathlib.Path(tmp) / "settings.toml"
        generate_settings(config, output_path)
        assert output_path.exists()
        content = output_path.read_text()
        assert "num_inputs = 2" in content
        assert "num_outputs = 2" in content

def test_generate_device_db():
    config_path = CONFIGS_DIR / "experiments" / "2in_2out.yaml"
    config = load_config(config_path)
    with tempfile.TemporaryDirectory() as tmp:
        output_path = pathlib.Path(tmp) / "device_db.py"
        generate_device_db(config, output_path)
        assert output_path.exists()
        content = output_path.read_text()
        assert '"DIO0"' in content
        assert '"DIO3"' in content

def test_build_gateware_dry_run():
    config_path = CONFIGS_DIR / "experiments" / "2in_2out.yaml"
    config = load_config(config_path)
    # Should not raise
    build_gateware(config, dry_run=True)