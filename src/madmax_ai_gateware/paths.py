from __future__ import annotations

from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
GATEWARE_BUILD_DIR = WORKSPACE_ROOT / "gateware_build"
CONFIG_DIR = GATEWARE_BUILD_DIR / "configs"
TEMPLATE_DIR = CONFIG_DIR / "templates"
DEFAULT_CONFIG = CONFIG_DIR / "experiments" / "2in_2out.yaml"
DEFAULT_DESCRIPTION_DIR = GATEWARE_BUILD_DIR / "descriptions"
DEFAULT_GENERATED_DIR = GATEWARE_BUILD_DIR / "generated"


def resolve_workspace_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return WORKSPACE_ROOT / candidate


def display_path(path: str | Path) -> str:
    resolved = resolve_workspace_path(path)
    try:
        return str(resolved.relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(resolved)
