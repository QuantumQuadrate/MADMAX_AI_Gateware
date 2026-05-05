import pytest
import pathlib
from madmax_ai_gateware.paths import WORKSPACE_ROOT, REPOS_DIR, CONFIGS_DIR

def test_workspace_paths():
    assert WORKSPACE_ROOT.exists()
    assert REPOS_DIR.exists()
    assert CONFIGS_DIR.exists()

def test_repo_paths():
    repos = ["madmax-artiq-env", "madmax-artiq-zynq", "madmax-entangler-core"]
    for repo in repos:
        assert (REPOS_DIR / repo).exists()