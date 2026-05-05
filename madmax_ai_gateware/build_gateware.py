import subprocess
from .config import Config

def build_gateware(config: Config, dry_run: bool = True):
    command = config.build.command_template.format(
        repositories=config.repositories.__dict__,
        target=config.target.__dict__,
        entangler=config.entangler.__dict__,
        hardware=config.hardware.__dict__,
        build=config.build.__dict__,
        experiment=config.experiment.__dict__
    )
    if dry_run or config.build.dry_run:
        print(f"Dry run: Would execute: {command}")
    else:
        try:
            subprocess.run(command, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Build failed: {e}")