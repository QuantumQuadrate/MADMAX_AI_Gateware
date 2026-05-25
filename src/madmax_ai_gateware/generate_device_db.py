from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .config import ExperimentConfig
from .paths import DEFAULT_GENERATED_DIR, TEMPLATE_DIR, display_path, resolve_workspace_path


def generate_device_db(
    cfg: ExperimentConfig,
    output: str | Path | None = None,
    *,
    core_host: str = "192.168.1.75",
) -> Path:
    output_path = resolve_workspace_path(output) if output else DEFAULT_GENERATED_DIR / "device_db.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False, keep_trailing_newline=True)
    template = env.get_template("device_db.py.j2")
    rendered = template.render(cfg=cfg, source_config=_source_config(cfg), core_host=core_host)
    output_path.write_text(rendered, encoding="utf-8")
    return output_path


def _source_config(cfg: ExperimentConfig) -> str:
    return display_path(cfg.source_path) if cfg.source_path else "<in-memory>"

