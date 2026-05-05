from jinja2 import Template
import pathlib
from .config import Config
from .paths import CONFIGS_DIR, GENERATED_DIR

def generate_settings(config: Config, output_path: pathlib.Path = None):
    if output_path is None:
        output_path = GENERATED_DIR / "settings.toml"
    template_path = CONFIGS_DIR / "templates" / "settings.toml.j2"
    with open(template_path, 'r') as f:
        template_content = f.read()
    template = Template(template_content)
    content = template.render(
        entangler=config.entangler,
        target=config.target,
        hardware=config.hardware
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(content)