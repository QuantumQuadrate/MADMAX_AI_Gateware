from madmax_ai_gateware.build_gateware import build_context, render_build_steps
from madmax_ai_gateware.config import load_config
from madmax_ai_gateware.paths import DEFAULT_CONFIG, WORKSPACE_ROOT, display_path


def test_gateware_build_uses_description_json_from_gateware_build_folder():
    cfg = load_config(DEFAULT_CONFIG)

    assert display_path(cfg.description_json_path) == "gateware_build/descriptions/entangler_1dio_2in_2out.json"
    assert build_context(cfg)["artiq_description_json"].endswith(
        "gateware_build/descriptions/entangler_1dio_2in_2out.json"
    )
    assert any("gateware_build/descriptions/entangler_1dio_2in_2out.json" in step for step in render_build_steps(cfg))


def test_entangler_overlay_combines_helper_with_moninj_overrides():
    integration = (
        WORKSPACE_ROOT
        / "repos"
        / "madmax-artiq-zynq"
        / "src"
        / "gateware"
        / "entangler_integration.py"
    ).read_text(encoding="utf-8")

    assert "phy_override_en.eq(helper_override_en | moninj_override_en)" in integration
    assert "Mux(helper_override_en, helper_override_o, moninj_override_o)" in integration
    assert "channel.overrides = [moninj_override_en, moninj_override_o" in integration
