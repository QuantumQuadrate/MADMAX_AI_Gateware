from madmax_ai_gateware.config import load_config
from madmax_ai_gateware.paths import DEFAULT_CONFIG


def test_example_yaml_loads():
    cfg = load_config(DEFAULT_CONFIG)

    assert cfg.experiment.name == "2in_2out"
    assert cfg.target.board == "kasli_soc"
    assert cfg.repositories.artiq_zynq_path == "repos/madmax-artiq-zynq"

