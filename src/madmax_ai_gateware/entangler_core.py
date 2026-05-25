from __future__ import annotations

import subprocess
from pathlib import Path

from .paths import resolve_workspace_path


ENTANGLER_CORE_PATH = resolve_workspace_path("repos/madmax-entangler-core")


def _core_path(path: str | Path | None = None) -> Path:
    return resolve_workspace_path(path) if path is not None else ENTANGLER_CORE_PATH


def list_entangler_branches(path: str | Path | None = None) -> list[str]:
    result = subprocess.run(
        ["git", "branch", "-a", "--format=%(refname:short)"],
        cwd=_core_path(path),
        check=True,
        capture_output=True,
        text=True,
    )
    branches: set[str] = set()
    for raw in result.stdout.splitlines():
        branch = raw.strip()
        if not branch or branch == "origin/HEAD":
            continue
        if branch.startswith("origin/"):
            branch = branch.removeprefix("origin/")
        branches.add(branch)
    return sorted(branches)


def current_entangler_branch(path: str | Path | None = None) -> str:
    repo = _core_path(path)
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    branch = result.stdout.strip()
    if branch:
        return branch
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def checkout_entangler_branch(branch: str, path: str | Path | None = None) -> str:
    repo = _core_path(path)
    branch = branch.strip()
    if not branch:
        raise ValueError("Entangler branch cannot be empty")

    current = current_entangler_branch(repo)
    if branch == current:
        return current

    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise RuntimeError(
            "madmax-entangler-core has uncommitted changes on "
            f"{current!r}; refusing to switch to {branch!r}. "
            "Select the current checkout in the mapper, or commit/stash the entangler-core changes first."
        )

    local = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo,
    )
    if local.returncode == 0:
        subprocess.run(["git", "checkout", branch], cwd=repo, check=True)
    else:
        remote = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"],
            cwd=repo,
        )
        if remote.returncode != 0:
            raise RuntimeError(f"Unknown entangler-core branch: {branch}")
        subprocess.run(["git", "checkout", "-B", branch, f"origin/{branch}"], cwd=repo, check=True)
    return current_entangler_branch(repo)


def entangler_override_args(path: str | Path | None = None) -> list[str]:
    return ["--override-input", "entangler-core", f"path:{_core_path(path)}"]
