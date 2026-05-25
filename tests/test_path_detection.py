from madmax_ai_gateware.paths import WORKSPACE_ROOT, display_path, resolve_workspace_path
from madmax_ai_gateware.submodules import SUBMODULES


def test_workspace_relative_path_detection():
    path = resolve_workspace_path("gateware_build/configs/experiments/2in_2out.yaml")

    assert path == WORKSPACE_ROOT / "gateware_build" / "configs" / "experiments" / "2in_2out.yaml"
    assert display_path(path) == "gateware_build/configs/experiments/2in_2out.yaml"


def test_expected_submodule_paths_are_registered():
    assert SUBMODULES["madmax-artiq-env"].as_posix() == "repos/madmax-artiq-env"
    assert SUBMODULES["madmax-artiq-zynq"].as_posix() == "repos/madmax-artiq-zynq"
    assert SUBMODULES["madmax-entangler-core"].as_posix() == "repos/madmax-entangler-core"
