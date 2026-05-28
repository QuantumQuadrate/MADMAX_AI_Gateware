from pathlib import Path

from madmax_ai_gateware.build_gateware import render_build_command
from madmax_ai_gateware.config import load_config
from madmax_ai_gateware.generate_artiq_description import generate_artiq_description
from madmax_ai_gateware.generate_device_db import generate_device_db
from madmax_ai_gateware.generate_entangler_settings import generate_entangler_settings
from madmax_ai_gateware.generate_experiment import generate_experiment
from madmax_ai_gateware.generate_settings import generate_settings
from madmax_ai_gateware.paths import DEFAULT_CONFIG


def test_generated_settings_contains_counts(tmp_path: Path):
    cfg = load_config(DEFAULT_CONFIG)
    output = generate_settings(cfg, tmp_path / "settings.toml")
    text = output.read_text(encoding="utf-8")

    assert "num_inputs = 2" in text
    assert "num_outputs = 2" in text


def test_generated_entangler_settings_contains_dynaconf_keys(tmp_path: Path):
    cfg = load_config(DEFAULT_CONFIG)
    output = generate_entangler_settings(cfg, tmp_path / "entangler_settings.toml")
    text = output.read_text(encoding="utf-8")

    assert "NUM_ENTANGLER_INPUT_SIGNALS = 2" in text
    assert "NUM_OUTPUT_CHANNELS = 2" in text


def test_generated_artiq_description_contains_entangler_peripheral(tmp_path: Path):
    cfg = load_config(DEFAULT_CONFIG)
    output = generate_artiq_description(cfg, tmp_path / "description.json")
    text = output.read_text(encoding="utf-8")

    assert '"target": "kasli_soc"' in text
    assert '"variant": "entangler_1dio_2in_2out"' in text
    assert '"type": "entangler"' in text
    assert '"ports": [' in text


def test_generated_device_db_contains_rtio_device_names(tmp_path: Path):
    cfg = load_config(DEFAULT_CONFIG)
    output = generate_device_db(cfg, tmp_path / "device_db.py")
    text = output.read_text(encoding="utf-8")

    assert '"entangler_input0"' in text
    assert '"entangler_input1"' in text
    assert '"entangler_output0"' in text
    assert '"entangler_output1"' in text


def test_generated_experiment_contains_configured_devices(tmp_path: Path):
    cfg = load_config(DEFAULT_CONFIG)
    output = generate_experiment(cfg, tmp_path)
    text = output.read_text(encoding="utf-8")

    assert 'self.setattr_device("entangler_input0")' in text
    assert 'self.setattr_device("entangler_output1")' in text
    compile(text, str(output), "exec")


def test_dry_run_build_command_generation():
    cfg = load_config(DEFAULT_CONFIG)
    command = render_build_command(cfg)

    assert "madmax-artiq-zynq" in command
    assert "scripts/build_from_json.sh" in command
    assert "entangler_settings.toml" in command
    assert "entangler_1dio_2in_2out.json" in command
    assert "standalone" in command
