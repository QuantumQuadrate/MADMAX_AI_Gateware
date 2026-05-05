import pathlib
from .config import Config
from .paths import EXPERIMENTS_DIR

def generate_experiment(config: Config, output_path: pathlib.Path = None):
    if output_path is None:
        output_path = EXPERIMENTS_DIR / f"{config.experiment.name}_test.py"
    experiment_code = f'''
from artiq.experiment import *

class {config.experiment.name.title()}Test(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        # Add DIO devices
        for pad in {config.hardware.input_pads + config.hardware.output_pads}:
            self.setattr_device(pad)

    @kernel
    def run(self):
        self.core.reset()
        # Test inputs and outputs
        # TODO: Implement actual test logic
        pass
'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(experiment_code)