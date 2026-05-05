from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .config import ExperimentConfig
from .paths import DEFAULT_GENERATED_DIR, TEMPLATE_DIR, display_path, resolve_workspace_path


def generate_settings(cfg: ExperimentConfig, output: str | Path | None = None) -> Path:
    output_path = resolve_workspace_path(output) if output else DEFAULT_GENERATED_DIR / "settings.toml"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False, keep_trailing_newline=True)
    template = env.get_template("settings.toml.j2")
    rendered = template.render(cfg=cfg, source_config=_source_config(cfg))
    output_path.write_text(rendered, encoding="utf-8")
    return output_path


def _source_config(cfg: ExperimentConfig) -> str:
    return display_path(cfg.source_path) if cfg.source_path else "<in-memory>"

