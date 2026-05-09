from pathlib import Path

from madmax_ai_gateware.build_gateware import render_build_command
from madmax_ai_gateware.config import load_config
from madmax_ai_gateware.artiq_description import make_description, validate_peripherals, write_artiq_description
from madmax_ai_gateware.generate_device_db import generate_device_db
from madmax_ai_gateware.generate_experiment import generate_experiment
from madmax_ai_gateware.generate_settings import generate_settings
from madmax_ai_gateware.paths import DEFAULT_CONFIG


def test_generated_settings_contains_counts(tmp_path: Path):
    cfg = load_config(DEFAULT_CONFIG)
    output = generate_settings(cfg, tmp_path / "settings.toml")
    text = output.read_text(encoding="utf-8")

    assert "num_inputs = 2" in text
    assert "num_outputs = 2" in text


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
    assert "kasli_soc.py" in command
    assert "entangler_1dio_2in_2out.json" in command


def test_generated_artiq_json_contains_entangler(tmp_path: Path):
    cfg = load_config(DEFAULT_CONFIG)
    output = write_artiq_description(cfg, tmp_path / "description.json")
    text = output.read_text(encoding="utf-8")

    assert '"target": "kasli_soc"' in text
    assert '"type": "entangler"' in text
    assert '"ports": [' in text


def test_dio_defaults_are_added_to_artiq_json():
    cfg = load_config(DEFAULT_CONFIG)
    description = make_description(cfg, peripherals=[{"type": "dio", "ports": [1]}])

    dio = description["peripherals"][0]
    assert dio["bank_direction_low"] == "input"
    assert dio["bank_direction_high"] == "output"
    assert dio["edge_counter"] is False


def test_entangler_accepts_multiple_eem_ports():
    errors = validate_peripherals(
        [{"type": "entangler", "ports": [0, 1], "uses_reference": False}],
        drtio_role="standalone",
    )

    assert errors == []


def test_generated_settings_contains_entangler_logic(tmp_path: Path):
    cfg = load_config(DEFAULT_CONFIG)
    output = generate_settings(cfg, tmp_path / "settings.toml")
    text = output.read_text(encoding="utf-8")

    assert "num_patterns_allowed = 2" in text
    assert "bitfield = 3" in text


def test_generated_atom_photon_parity_experiment_uses_parity_driver_api(tmp_path: Path):
    cfg = load_config(Path("configs/experiments/atom_photon_parity_6.yaml"))
    output = generate_experiment(cfg, tmp_path)
    text = output.read_text(encoding="utf-8")

    assert "set_num_attempts" in text
    assert "set_branch_done_delay_mu" in text
    assert "set_patterns" not in text
    compile(text, str(output), "exec")
