import pathlib
import subprocess
from .paths import REPOS_DIR

def check_submodules() -> List[str]:
    issues = []
    repos = ["madmax-artiq-env", "madmax-artiq-zynq", "madmax-entangler-core"]
    for repo in repos:
        repo_path = REPOS_DIR / repo
        if not repo_path.exists():
            issues.append(f"Repository {repo} directory missing")
        elif not (repo_path / ".git").exists():
            issues.append(f"Repository {repo} not initialized as submodule")
    return issues

def init_submodules():
    try:
        subprocess.run(["git", "submodule", "update", "--init", "--recursive"], check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to initialize submodules: {e}")