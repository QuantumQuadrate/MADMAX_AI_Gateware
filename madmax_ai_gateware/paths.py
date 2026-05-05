from __future__ import annotations

from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = WORKSPACE_ROOT / "configs"
TEMPLATE_DIR = CONFIG_DIR / "templates"
DEFAULT_CONFIG = CONFIG_DIR / "experiments" / "2in_2out.yaml"
DEFAULT_GENERATED_DIR = WORKSPACE_ROOT / "build" / "generated"


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

