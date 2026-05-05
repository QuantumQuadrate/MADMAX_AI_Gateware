import pathlib
import os

WORKSPACE_ROOT = pathlib.Path(__file__).parent.parent
REPOS_DIR = WORKSPACE_ROOT / "repos"
CONFIGS_DIR = WORKSPACE_ROOT / "configs"
BUILD_DIR = WORKSPACE_ROOT / "build"
GENERATED_DIR = BUILD_DIR / "generated"
EXPERIMENTS_DIR = GENERATED_DIR / "experiments"

def get_repo_path(repo_name: str) -> pathlib.Path:
    return REPOS_DIR / repo_name

def ensure_build_dirs():
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)