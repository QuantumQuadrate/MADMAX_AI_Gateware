from __future__ import annotations

import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from .paths import WORKSPACE_ROOT, display_path


ENTANGLER_CORE_DIR = WORKSPACE_ROOT / "repos" / "madmax-entangler-core"
ARTIQ_ZYNQ_DIR = WORKSPACE_ROOT / "repos" / "madmax-artiq-zynq"
ARTIQ_ENV_DIR = WORKSPACE_ROOT / "repos" / "madmax-artiq-env"
REQUEST_DIR = WORKSPACE_ROOT / "ai" / "requests"
CONFIG_EXPERIMENT_DIR = WORKSPACE_ROOT / "configs" / "experiments"

GITHUB_ENTANGLER_URL = "git+https://github.com/QuantumQuadrate/madmax-entangler-core.git"


def custom_logic_state() -> dict[str, Any]:
    return {
        "branches": _git_lines(["branch", "--format=%(refname:short)"], ENTANGLER_CORE_DIR),
        "current_branch": _git_one(["branch", "--show-current"], ENTANGLER_CORE_DIR),
        "entangler_status": _git_lines(["status", "--short"], ENTANGLER_CORE_DIR)[:40],
        "zynq_status": _git_lines(["status", "--short"], ARTIQ_ZYNQ_DIR)[:40],
        "artiq_envs": _list_artiq_envs(),
        "flake_entangler_url": _current_flake_entangler_url(),
        "codex_available": bool(shutil.which("codex")),
        "request_dir": display_path(REQUEST_DIR),
    }


def write_custom_logic_request(spec: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_spec(spec)
    REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    path = REQUEST_DIR / f"custom_logic_{normalized['slug']}.md"
    prompt = _render_codex_prompt(normalized)
    path.write_text(prompt, encoding="utf-8")
    return {
        "ok": True,
        "path": display_path(path),
        "prompt": prompt,
        "slug": normalized["slug"],
        "branch": normalized["branch"],
    }


def scaffold_custom_logic(spec: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_spec(spec)
    log: list[str] = []
    paths: list[str] = []

    request = write_custom_logic_request(normalized)
    paths.append(request["path"])
    log.append(f"Wrote Codex request: {request['path']}")

    if normalized["create_branch"]:
        log.extend(_ensure_entangler_branch(normalized["base_branch"], normalized["branch"]))

    if normalized["scaffold_core"]:
        paths.extend(_scaffold_core_files(normalized, log))

    if normalized["scaffold_env"]:
        paths.extend(_scaffold_env(normalized, log))

    if normalized["scaffold_config"]:
        paths.append(_scaffold_experiment_config(normalized, log))

    if normalized["flake_mode"] != "none":
        paths.append(update_flake_input(normalized["flake_mode"], normalized["branch"])["path"])
        log.append(f"Updated madmax-artiq-zynq flake input in {display_path(ARTIQ_ZYNQ_DIR / 'flake.nix')}")

    return {
        "ok": True,
        "slug": normalized["slug"],
        "branch": normalized["branch"],
        "paths": paths,
        "prompt": request["prompt"],
        "log": "\n".join(log),
    }


def update_flake_input(mode: str, branch: str) -> dict[str, Any]:
    if mode not in {"local_path", "remote_branch"}:
        raise ValueError("flake mode must be local_path or remote_branch")
    flake_path = ARTIQ_ZYNQ_DIR / "flake.nix"
    text = flake_path.read_text(encoding="utf-8")
    if mode == "local_path":
        url = "path:../madmax-entangler-core"
    else:
        url = f"{GITHUB_ENTANGLER_URL}?ref={branch}"
    new_text, count = re.subn(
        r'(inputs\.entangler-core\s*=\s*\{\s*\n\s*url\s*=\s*")[^"]+(";)',
        rf"\1{url}\2",
        text,
        count=1,
    )
    if count != 1:
        raise ValueError("Could not find inputs.entangler-core.url in madmax-artiq-zynq/flake.nix")
    flake_path.write_text(new_text, encoding="utf-8")
    return {"ok": True, "path": display_path(flake_path), "url": url}


def verification_commands(slug: str, *, include_nix: bool = False) -> list[str]:
    safe_slug = _slugify(slug)
    config = f"configs/experiments/{safe_slug}.yaml"
    commands = [
        f"pytest repos/madmax-entangler-core/test/test_{safe_slug}*.py",
        f"uv run madmax validate --config {config}",
        f"uv run madmax generate-settings --config {config}",
        f"uv run madmax generate-device-db --config {config}",
        f"uv run madmax generate-experiment --config {config}",
        f"uv run madmax build-gateware --config {config} --dry-run",
    ]
    if include_nix:
        commands.insert(1, "cd repos/madmax-artiq-zynq && nix flake lock --update-input entangler-core")
        commands.insert(2, "cd repos/madmax-artiq-zynq && nix flake check")
    return commands


def run_command_stream(command: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        command,
        cwd=WORKSPACE_ROOT,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def _normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    logic_name = str(spec.get("logic_name") or "").strip()
    if not logic_name:
        raise ValueError("logic_name is required")
    slug = _slugify(logic_name)
    if not slug:
        raise ValueError("logic_name must contain at least one letter or number")
    branch = str(spec.get("branch") or f"feature/{slug.replace('_', '-')}").strip()
    base_branch = str(spec.get("base_branch") or "artiq-integration").strip()
    flake_mode = str(spec.get("flake_mode") or "local_path").strip()
    if flake_mode not in {"local_path", "remote_branch", "none"}:
        raise ValueError("flake_mode must be local_path, remote_branch, or none")
    return {
        "logic_name": logic_name,
        "slug": slug,
        "class_name": _pascal_case(slug),
        "branch": branch,
        "base_branch": base_branch,
        "description": str(spec.get("description") or "").strip(),
        "required_behavior": str(spec.get("required_behavior") or "").strip(),
        "inputs": str(spec.get("inputs") or "").strip(),
        "outputs": str(spec.get("outputs") or "").strip(),
        "success_failure_rules": str(spec.get("success_failure_rules") or "").strip(),
        "test_behavior": str(spec.get("test_behavior") or "").strip(),
        "num_inputs": _positive_int(spec.get("num_inputs"), default=2),
        "num_outputs": _positive_int(spec.get("num_outputs"), default=2),
        "flake_mode": flake_mode,
        "create_branch": bool(spec.get("create_branch", True)),
        "scaffold_core": bool(spec.get("scaffold_core", True)),
        "scaffold_env": bool(spec.get("scaffold_env", True)),
        "scaffold_config": bool(spec.get("scaffold_config", True)),
    }


def _render_codex_prompt(spec: dict[str, Any]) -> str:
    return textwrap.dedent(
        f"""\
        # Custom Entangler Logic Request: {spec['logic_name']}

        Create custom entangler logic named `{spec['slug']}`.

        Base branch: `{spec['base_branch']}`
        Target branch: `{spec['branch']}`

        ## Description

        {spec['description'] or 'TODO: describe the experiment goal.'}

        ## Required Behavior

        {spec['required_behavior'] or 'TODO: define the gateware behavior.'}

        ## Inputs

        {spec['inputs'] or f'TODO: define {spec["num_inputs"]} inputs.'}

        ## Outputs

        {spec['outputs'] or f'TODO: define {spec["num_outputs"]} outputs.'}

        ## Success And Failure Rules

        {spec['success_failure_rules'] or 'TODO: define success, retry, timeout, and failure behavior.'}

        ## Test Experiment Behavior

        {spec['test_behavior'] or 'TODO: define smoke, loopback, timing-scan, stress, and benchmark expectations.'}

        ## Implementation Expectations

        - Work in `repos/madmax-entangler-core` on branch `{spec['branch']}`.
        - Keep the legacy entangler core stable unless the requested behavior is truly reusable.
        - Passthrough is required for every custom design: when the mode is disabled (`enable = 0`), DIO channels owned by the custom logic must behave like normal ARTIQ TTL inputs/outputs wherever physically possible.
        - If any owned DIO channel cannot be passed through, document it in the gateware design, JSON/card options, runtime driver, and tests.
        - Prefer isolated files for this mode:
          - `entangler/{spec['slug']}_core.py`
          - `entangler/{spec['slug']}_phy.py`
          - `entangler/{spec['slug']}_driver.py`
          - `entangler/{spec['slug']}_registers.py`
        - Add Migen/Python tests under `repos/madmax-entangler-core/test/`.
        - Keep `repos/madmax-artiq-zynq/flake.nix` pointed at the selected entangler-core branch or local path.
        - Keep runtime files in `repos/madmax-artiq-env/{spec['slug']}/`.
        - Keep the generated experiment config in `configs/experiments/{spec['slug']}.yaml`.
        - Run the verification ladder before suggesting a real gateware build or hardware flashing.
        """
    )


def _ensure_entangler_branch(base_branch: str, branch: str) -> list[str]:
    log: list[str] = []
    existing = set(_git_lines(["branch", "--format=%(refname:short)"], ENTANGLER_CORE_DIR))
    if branch in existing:
        _run_checked(["git", "checkout", branch], ENTANGLER_CORE_DIR)
        log.append(f"Checked out existing entangler-core branch: {branch}")
        return log
    _run_checked(["git", "checkout", base_branch], ENTANGLER_CORE_DIR)
    _run_checked(["git", "checkout", "-b", branch], ENTANGLER_CORE_DIR)
    log.append(f"Created entangler-core branch {branch} from {base_branch}")
    return log


def _scaffold_core_files(spec: dict[str, Any], log: list[str]) -> list[str]:
    class_name = spec["class_name"]
    slug = spec["slug"]
    files = {
        ENTANGLER_CORE_DIR / "entangler" / f"{slug}_registers.py": _registers_template(class_name),
        ENTANGLER_CORE_DIR / "entangler" / f"{slug}_core.py": _core_template(class_name),
        ENTANGLER_CORE_DIR / "entangler" / f"{slug}_phy.py": _phy_template(class_name, slug),
        ENTANGLER_CORE_DIR / "entangler" / f"{slug}_driver.py": _driver_template(class_name, slug),
        ENTANGLER_CORE_DIR / "test" / f"test_{slug}_core.py": _core_test_template(class_name, slug),
    }
    written: list[str] = []
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            log.append(f"Kept existing file: {display_path(path)}")
            continue
        path.write_text(content, encoding="utf-8")
        written.append(display_path(path))
        log.append(f"Wrote scaffold: {display_path(path)}")
    return written


def _scaffold_env(spec: dict[str, Any], log: list[str]) -> list[str]:
    slug = spec["slug"]
    env_dir = ARTIQ_ENV_DIR / slug
    repo_dir = env_dir / "repository"
    repo_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    source_pyproject = ARTIQ_ENV_DIR / "entangler" / "pyproject.toml"
    if source_pyproject.exists():
        pyproject = source_pyproject.read_text(encoding="utf-8")
        pyproject = re.sub(
            r'name\s*=\s*"[^"]+"',
            f'name = "madmax-artiq-{slug.replace("_", "-")}-env"',
            pyproject,
            count=1,
        )
        dependency = _entangler_dependency_for_env(spec)
        pyproject = re.sub(r'"entangler\s*@\s*[^"]+"', f'"{dependency}"', pyproject, count=1)
    else:
        pyproject = textwrap.dedent(
            f"""\
            [project]
            name = "madmax-artiq-{slug.replace('_', '-')}-env"
            version = "0.1.0"
            requires-python = "==3.9.*"
            dependencies = [
              "{_entangler_dependency_for_env(spec)}",
            ]
            """
        )

    env_files = {
        env_dir / "pyproject.toml": pyproject,
        env_dir / "README.md": _env_readme_template(spec),
        env_dir / "device_db.py": _device_db_template(spec),
        env_dir / "run_artiq.sh": _run_artiq_template(slug),
        repo_dir / f"{slug}_smoke.py": _experiment_template(spec, "smoke"),
        repo_dir / f"{slug}_loopback.py": _experiment_template(spec, "loopback"),
        repo_dir / f"{slug}_timing_scan.py": _experiment_template(spec, "timing_scan"),
        repo_dir / f"{slug}_stress_test.py": _experiment_template(spec, "stress_test"),
        repo_dir / f"{slug}_benchmark.py": _experiment_template(spec, "benchmark"),
    }
    settings_source = ARTIQ_ENV_DIR / "entangler" / "settings.toml"
    if settings_source.exists():
        env_files[env_dir / "settings.toml"] = settings_source.read_text(encoding="utf-8")
    for path, content in env_files.items():
        if path.exists():
            log.append(f"Kept existing env file: {display_path(path)}")
            continue
        path.write_text(content, encoding="utf-8")
        if path.name == "run_artiq.sh":
            path.chmod(0o755)
        written.append(display_path(path))
        log.append(f"Wrote ARTIQ env file: {display_path(path)}")
    return written


def _scaffold_experiment_config(spec: dict[str, Any], log: list[str]) -> str:
    slug = spec["slug"]
    num_inputs = spec["num_inputs"]
    num_outputs = spec["num_outputs"]
    if num_inputs + num_outputs > 8:
        raise ValueError("The current experiment YAML scaffold supports one 8-channel DIO bank; keep inputs + outputs <= 8 or disable experiment YAML scaffolding.")
    total = min(num_inputs + num_outputs, 8)
    input_pads = [f"dio{i}" for i in range(min(num_inputs, total))]
    output_pads = [f"dio{i}" for i in range(len(input_pads), min(total, len(input_pads) + num_outputs))]
    if len(output_pads) < num_outputs:
        output_pads = [f"dio{i}" for i in range(num_inputs, num_inputs + num_outputs)]
    config_path = CONFIG_EXPERIMENT_DIR / f"{slug}.yaml"
    if config_path.exists():
        log.append(f"Kept existing config: {display_path(config_path)}")
        return display_path(config_path)
    input_names = "\n".join(f"    - input{i}" for i in range(num_inputs))
    output_names = "\n".join(f"    - output{i}" for i in range(num_outputs))
    input_pad_text = "\n".join(f"    - {pad}" for pad in input_pads)
    output_pad_text = "\n".join(f"    - {pad}" for pad in output_pads)
    pattern_inputs = ", ".join(str(i) for i in range(num_inputs))
    config_path.write_text(
        textwrap.dedent(
            f"""\
            experiment:
              name: {slug}
              description: Custom entangler logic scaffold for {spec['logic_name']}.

            target:
              board: kasli_soc
              artiq_version: 7
              variant: {slug}
              hw_rev: v1.0
              drtio_role: standalone
              rtio_frequency: 125000000.0

            repositories:
              artiq_env_path: repos/madmax-artiq-env
              entangler_core_path: repos/madmax-entangler-core
              entangler_core_branch: {spec['branch']}
              artiq_zynq_path: repos/madmax-artiq-zynq

            hardware:
              dio_eem: 0
              input_pads:
            {input_pad_text}
              output_pads:
            {output_pad_text}

            entangler:
              num_inputs: {num_inputs}
              num_outputs: {num_outputs}
              num_generic_inputs: 0
              num_patterns_allowed: 2
              coincidence_window_mu: 250
              timeout_mu: 10000
              fast_branch: true
              requested_goal: custom entangler logic
              input_names:
            {input_names}
              output_names:
            {output_names}
              patterns:
                - name: all_inputs
                  inputs: [{pattern_inputs}]

            build:
              output_dir: build/generated
              dry_run: true
              command_template: "cd {{artiq_zynq_path}} && nix develop --command bash -lc 'cd src && python gateware/{{board}}.py -g {{gateware_build_dir}} {{artiq_description_json}}'"
            """
        ),
        encoding="utf-8",
    )
    log.append(f"Wrote experiment config: {display_path(config_path)}")
    return display_path(config_path)


def _current_flake_entangler_url() -> str:
    flake_path = ARTIQ_ZYNQ_DIR / "flake.nix"
    if not flake_path.exists():
        return ""
    match = re.search(r'inputs\.entangler-core\s*=\s*\{\s*\n\s*url\s*=\s*"([^"]+)"', flake_path.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def _list_artiq_envs() -> list[str]:
    if not ARTIQ_ENV_DIR.exists():
        return []
    return sorted(
        path.name
        for path in ARTIQ_ENV_DIR.iterdir()
        if path.is_dir() and ((path / "pyproject.toml").exists() or (path / "settings.toml").exists())
    )


def _git_one(args: list[str], cwd: Path) -> str:
    lines = _git_lines(args, cwd)
    return lines[0] if lines else ""


def _git_lines(args: list[str], cwd: Path) -> list[str]:
    try:
        result = subprocess.run(["git", *args], cwd=cwd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return []
    text = result.stdout if result.stdout.strip() else result.stderr
    return [line.strip() for line in text.splitlines() if line.strip()]


def _run_checked(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "command failed").strip())


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if slug and slug[0].isdigit():
        slug = f"logic_{slug}"
    return slug


def _pascal_case(slug: str) -> str:
    return "".join(part.capitalize() for part in slug.split("_") if part)


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, parsed)


def _entangler_dependency_for_env(spec: dict[str, Any]) -> str:
    if spec["flake_mode"] == "remote_branch":
        return f"entangler @ git+https://github.com/QuantumQuadrate/madmax-entangler-core.git@{spec['branch']}"
    return f"entangler @ {ENTANGLER_CORE_DIR.as_uri()}"


def _registers_template(class_name: str) -> str:
    return textwrap.dedent(
        f'''\
        """Register constants for the {class_name} custom entangler mode."""

        from __future__ import annotations

        import enum


        class {class_name}Write(enum.IntEnum):
            CONFIG = 0x00
            CONTROL = 0x01


        class {class_name}Read(enum.IntEnum):
            STATUS = 0x80
            RESULT = 0x81
        '''
    )


def _core_template(class_name: str) -> str:
    return textwrap.dedent(
        f'''\
        """Custom entangler gateware core for {class_name}."""

        from __future__ import annotations

        from migen import If
        from migen import Module
        from migen import Signal


        class {class_name}Core(Module):
            """Scaffold for custom timing-critical entangler logic."""

            def __init__(self):
                self.start_stb = Signal()
                self.clear = Signal()
                self.running = Signal()
                self.done_stb = Signal()
                self.success = Signal()
                self.result = Signal(32)

                done_d = Signal()
                self.sync += [
                    done_d.eq(self.done_stb),
                    If(
                        self.clear,
                        self.running.eq(0),
                        self.done_stb.eq(0),
                        self.success.eq(0),
                        self.result.eq(0),
                    ).Elif(
                        self.start_stb,
                        self.running.eq(1),
                        self.done_stb.eq(1),
                        self.success.eq(1),
                        self.result.eq(1),
                    ).Else(
                        self.done_stb.eq(0),
                        If(done_d, self.running.eq(0)),
                    ),
                ]
        '''
    )


def _phy_template(class_name: str, slug: str) -> str:
    return textwrap.dedent(
        f'''\
        """RTIO PHY scaffold for the {class_name} custom entangler mode."""

        from __future__ import annotations

        from artiq.gateware.rtio import rtlink
        from migen import Cat
        from migen import ClockDomainsRenamer
        from migen import If
        from migen import Module
        from migen import Signal

        from entangler.{slug}_core import {class_name}Core
        from entangler.{slug}_registers import {class_name}Read, {class_name}Write


        class {class_name}(Module):
            """ARTIQ-facing scaffold for custom gateware."""

            def __init__(self, core_link_pads, output_pads, passthrough_sigs, input_phys, reference_phy=None, simulate=False):
                self.enable = Signal()
                self.rtlink = rtlink.Interface(
                    rtlink.OInterface(data_width=32, address_width=8, enable_replace=False),
                    rtlink.IInterface(data_width=32, timestamped=True),
                )
                self.submodules.core = ClockDomainsRenamer("rio")({class_name}Core())
                self.comb += self.rtlink.o.busy.eq(0)
                # Required design rule: when self.enable is 0, route owned DIO
                # channels through normal ARTIQ passthrough wherever possible.
                # The concrete signal wiring is mode-specific.
                self.comb += [
                    self.core.start_stb.eq(
                        self.rtlink.o.stb
                        & (self.rtlink.o.address == int({class_name}Write.CONTROL))
                        & self.rtlink.o.data[0]
                    ),
                    self.core.clear.eq(
                        self.rtlink.o.stb
                        & (self.rtlink.o.address == int({class_name}Write.CONTROL))
                        & self.rtlink.o.data[1]
                    ),
                ]
                self.sync.rio += If(
                    self.rtlink.o.stb & (self.rtlink.o.address == int({class_name}Write.CONFIG)),
                    self.enable.eq(self.rtlink.o.data[0]),
                )
                status = Signal(32)
                self.comb += status.eq(Cat(self.enable, self.core.running, self.core.success))
                self.comb += [
                    self.rtlink.i.stb.eq(self.core.done_stb),
                    self.rtlink.i.data.eq(self.core.result),
                ]
        '''
    )


def _driver_template(class_name: str, slug: str) -> str:
    return textwrap.dedent(
        f'''\
        """ARTIQ driver scaffold for the {class_name} custom entangler mode."""

        from __future__ import annotations

        try:
            from artiq.coredevice.rtio import rtio_input_timestamped_data, rtio_output
            from artiq.language.core import delay_mu, kernel
            from artiq.language.types import TInt32, TInt64, TTuple
        except ImportError:
            def kernel(function):
                return function
            TInt32 = int
            TInt64 = int
            def TTuple(_types):
                return tuple

        from entangler.{slug}_registers import {class_name}Read, {class_name}Write


        class {class_name}Entangler:
            kernel_invariants = {{"core", "channel", "ref_period_mu"}}

            def __init__(self, dmgr, channel, core_device="core"):
                self.core = dmgr.get(core_device)
                self.channel = channel
                self.ref_period_mu = self.core.seconds_to_mu(self.core.coarse_ref_period)

            @kernel
            def _write(self, addr: TInt32, value: TInt32):
                rtio_output((self.channel << 8) | addr, value)
                delay_mu(self.ref_period_mu)

            @kernel
            def set_config(self, enable: TInt32 = 0):
                self._write(int({class_name}Write.CONFIG), enable & 0x1)

            @kernel
            def clear(self):
                self._write(int({class_name}Write.CONTROL), 0x2)

            @kernel
            def start(self):
                self._write(int({class_name}Write.CONTROL), 0x1)

            @kernel
            def run_mu(self) -> TTuple([TInt64, TInt32]):
                self.start()
                return rtio_input_timestamped_data(-1, self.channel)
        '''
    )


def _core_test_template(class_name: str, slug: str) -> str:
    return textwrap.dedent(
        f'''\
        """Smoke tests for the {class_name} custom entangler scaffold."""

        from entangler.{slug}_core import {class_name}Core


        def test_{slug}_core_instantiates():
            dut = {class_name}Core()
            assert dut.start_stb is not None
            assert dut.done_stb is not None
        '''
    )


def _env_readme_template(spec: dict[str, Any]) -> str:
    return textwrap.dedent(
        f"""\
        # {spec['logic_name']} ARTIQ Environment

        This environment is paired with entangler-core branch `{spec['branch']}`.

        ## Setup

        ```bash
        uv sync
        ./run_artiq.sh
        ```

        Keep `settings.toml`, `device_db.py`, and the flashed bitstream aligned.
        """
    )


def _device_db_template(spec: dict[str, Any]) -> str:
    class_name = spec["class_name"]
    slug = spec["slug"]
    return textwrap.dedent(
        f'''\
        """Device DB scaffold for {spec['logic_name']}."""

        device_db = {{
            "core": {{
                "type": "local",
                "module": "artiq.coredevice.core",
                "class": "Core",
                "arguments": {{"host": "192.168.1.129"}},
            }},
            "{slug}": {{
                "type": "local",
                "module": "entangler.{slug}_driver",
                "class": "{class_name}Entangler",
                "arguments": {{"channel": 0}},
            }},
        }}
        '''
    )


def _run_artiq_template(slug: str) -> str:
    return textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail

        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        cd "$SCRIPT_DIR"

        export SETTINGS_FILE_FOR_DYNACONF="$SCRIPT_DIR/settings.toml"
        export PYTHONNOUSERSITE=1

        if [[ ! -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
            echo "Missing virtualenv. Run 'uv sync' in $SCRIPT_DIR first." >&2
            exit 1
        fi

        "$SCRIPT_DIR/.venv/bin/python" -I -m artiq.frontend.artiq_run \\
          --device-db "$SCRIPT_DIR/device_db.py" \\
          --dataset-db "$SCRIPT_DIR/dataset_db.pyon" \\
          "$SCRIPT_DIR/repository/{slug}_smoke.py"
        """
    )


def _experiment_template(spec: dict[str, Any], kind: str) -> str:
    class_name = "".join(part.capitalize() for part in kind.split("_"))
    slug = spec["slug"]
    return textwrap.dedent(
        f'''\
        """{kind.replace("_", " ").title()} experiment scaffold for {spec['logic_name']}."""

        try:
            from artiq.experiment import EnvExperiment, kernel
        except ImportError:
            class EnvExperiment:
                pass
            def kernel(function):
                return function


        class {spec['class_name']}{class_name}(EnvExperiment):
            def build(self):
                self.setattr_device("core")
                self.setattr_device("{slug}")

            @kernel
            def run(self):
                self.core.reset()
                self.{slug}.set_config(1)
                self.{slug}.clear()
                _timestamp, _result = self.{slug}.run_mu()
                self.{slug}.set_config(0)
        '''
    )
