from __future__ import annotations

import subprocess
from pathlib import Path

from .paths import WORKSPACE_ROOT

SUBMODULES = {
    "madmax-artiq-env": Path("repos/madmax-artiq-env"),
    "madmax-artiq-zynq": Path("repos/madmax-artiq-zynq"),
    "madmax-entangler-core": Path("repos/madmax-entangler-core"),
}


def check_submodules() -> list[str]:
    issues: list[str] = []
    for name, relative_path in SUBMODULES.items():
        path = WORKSPACE_ROOT / relative_path
        if not path.exists():
            issues.append(f"{name} is missing at {relative_path}")
        elif not any(path.iterdir()):
            issues.append(f"{name} exists but is empty at {relative_path}")
        elif not (path / ".git").exists():
            issues.append(f"{name} is present but does not look like an initialized submodule")
    return issues


def init_submodules() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=WORKSPACE_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

