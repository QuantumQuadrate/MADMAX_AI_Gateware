from __future__ import annotations

import json
import shlex
import subprocess
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .artiq_description import (
    CARD_DEFINITIONS,
    card_default_options,
    default_entangler_peripherals,
    make_description,
    validate_peripherals,
    write_artiq_description,
)
from .build_gateware import firmware_name, render_build_steps
from .config import ExperimentConfig, load_config
from .custom_logic import (
    custom_logic_state,
    run_command_stream,
    scaffold_custom_logic,
    update_flake_input,
    verification_commands,
    write_custom_logic_request,
)
from .entangler_core import checkout_entangler_branch, current_entangler_branch, list_entangler_branches
from .entangler_settings import write_entangler_settings
from .paths import DEFAULT_CONFIG, WORKSPACE_ROOT, display_path


_BUILD_LOCK = threading.Lock()
_BUILD_JOB: dict[str, Any] = {
    "running": False,
    "status": "idle",
    "log": "",
    "returncode": None,
}

_CUSTOM_LOCK = threading.Lock()
_CUSTOM_JOB: dict[str, Any] = {
    "running": False,
    "status": "idle",
    "log": "",
    "returncode": None,
}


def run_web_gui(
    config_path: str | Path = DEFAULT_CONFIG,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    cfg = load_config(config_path)

    class Handler(WebGuiHandler):
        config = cfg

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{server.server_port}"
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(f"{url}/?v={int(time.time())}")).start()
    print(f"MADMAX browser GUI running at {url}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


class WebGuiHandler(BaseHTTPRequestHandler):
    config: ExperimentConfig

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_text(HTML, content_type="text/html; charset=utf-8")
        elif parsed.path == "/api/state":
            self._send_json(self._state())
        elif parsed.path == "/api/build-plan":
            self._send_json({"lines": render_build_steps(self.config)})
        elif parsed.path == "/api/build-status":
            self._send_json(_job_snapshot())
        elif parsed.path == "/api/custom-logic/state":
            self._send_json(custom_logic_state())
        elif parsed.path == "/api/custom-logic/job-status":
            self._send_json(_custom_job_snapshot())
        elif parsed.path == "/api/entangler-branches":
            self._send_json(
                {
                    "branches": list_entangler_branches(),
                    "current": current_entangler_branch(),
                    "selected": self.config.repositories.entangler_core_branch,
                }
            )
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/api/preview":
                body = self._read_json()
                cfg = self._config_from_body(body)
                peripherals = body.get("peripherals", [])
                errors = validate_peripherals(peripherals, drtio_role=cfg.target.drtio_role)
                self._send_json(
                    {
                        "description": make_description(cfg, peripherals=peripherals),
                        "errors": errors,
                        "build_plan": render_build_steps(cfg),
                    }
                )
            elif parsed.path == "/api/save-json":
                body = self._read_json()
                cfg = self._config_from_body(body)
                peripherals = body.get("peripherals", [])
                errors = validate_peripherals(peripherals, drtio_role=cfg.target.drtio_role)
                if errors:
                    self._send_json({"ok": False, "errors": errors}, status=HTTPStatus.BAD_REQUEST)
                    return
                output = body.get("output") or None
                path = write_artiq_description(cfg, output, peripherals=peripherals)
                settings_path = write_entangler_settings(cfg)
                self._send_json({"ok": True, "path": display_path(path), "settings_path": display_path(settings_path)})
            elif parsed.path == "/api/checkout-entangler":
                body = self._read_json()
                branch = body.get("branch", "")
                current = checkout_entangler_branch(branch)
                self._send_json({"ok": True, "current": current})
            elif parsed.path == "/api/copy-command":
                body = self._read_json()
                cfg = self._config_from_body(body)
                peripherals = body.get("peripherals", [])
                errors = validate_peripherals(peripherals, drtio_role=cfg.target.drtio_role)
                if errors:
                    self._send_json({"ok": False, "errors": errors}, status=HTTPStatus.BAD_REQUEST)
                    return
                path = write_artiq_description(cfg, body.get("output") or None, peripherals=peripherals)
                settings_path = write_entangler_settings(cfg)
                self._send_json({"ok": True, "path": display_path(path), "settings_path": display_path(settings_path), "command": _copy_paste_command(cfg)})
            elif parsed.path == "/api/run-build":
                body = self._read_json()
                cfg = self._config_from_body(body)
                peripherals = body.get("peripherals", [])
                errors = validate_peripherals(peripherals, drtio_role=cfg.target.drtio_role)
                if errors:
                    self._send_json({"ok": False, "errors": errors}, status=HTTPStatus.BAD_REQUEST)
                    return
                path = write_artiq_description(cfg, body.get("output") or None, peripherals=peripherals)
                settings_path = write_entangler_settings(cfg)
                started = _start_build_job(cfg, path, settings_path)
                status = HTTPStatus.OK if started["ok"] else HTTPStatus.CONFLICT
                self._send_json(started, status=status)
            elif parsed.path == "/api/custom-logic/request":
                body = self._read_json()
                self._send_json(write_custom_logic_request(body))
            elif parsed.path == "/api/custom-logic/scaffold":
                body = self._read_json()
                self._send_json(scaffold_custom_logic(body))
            elif parsed.path == "/api/custom-logic/update-flake":
                body = self._read_json()
                self._send_json(update_flake_input(body.get("flake_mode", "local_path"), body.get("branch", "")))
            elif parsed.path == "/api/custom-logic/run-checks":
                body = self._read_json()
                started = _start_custom_checks(
                    body.get("logic_name", ""),
                    include_nix=bool(body.get("include_nix", False)),
                )
                status = HTTPStatus.OK if started["ok"] else HTTPStatus.CONFLICT
                self._send_json(started, status=status)
            elif parsed.path == "/api/custom-logic/run-codex":
                body = self._read_json()
                started = _start_codex_task(body)
                status = HTTPStatus.OK if started["ok"] else HTTPStatus.CONFLICT
                self._send_json(started, status=status)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json({"ok": False, "errors": [str(exc)]}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _state(self) -> dict[str, Any]:
        return {
            "config": self.config.model_dump(mode="json", exclude={"source_path"}),
            "source": display_path(self.config.source_path) if self.config.source_path else None,
            "cards": [
                {
                    "type": definition.type,
                    "label": definition.label,
                    "port_count": definition.port_count,
                    "min_ports": definition.min_ports,
                    "default_options": card_default_options(definition.type, self.config),
                    "requires_drtio": definition.requires_drtio,
                }
                for definition in CARD_DEFINITIONS.values()
            ],
            "peripherals": default_entangler_peripherals(self.config),
            "default_output": display_path(self.config.output_dir / f"{self.config.target.variant}.json"),
        }

    def _config_from_body(self, body: dict[str, Any]) -> ExperimentConfig:
        data = self.config.model_dump(mode="json", exclude={"source_path"})
        target = body.get("target", {})
        for key in ["variant", "hw_rev", "drtio_role", "rtio_frequency"]:
            if key in target:
                data["target"][key] = target[key]
        repositories = body.get("repositories", {})
        if "entangler_core_branch" in repositories:
            data["repositories"]["entangler_core_branch"] = repositories["entangler_core_branch"]
        entangler = body.get("entangler", {})
        for key in [
            "num_inputs",
            "num_outputs",
            "num_generic_inputs",
            "num_patterns_allowed",
            "coincidence_window_mu",
            "timeout_mu",
            "fast_branch",
            "input_names",
            "output_names",
            "patterns",
        ]:
            if key in entangler:
                data["entangler"][key] = entangler[key]
        if "num_inputs" in data["entangler"] and "num_outputs" in data["entangler"]:
            num_inputs = int(data["entangler"]["num_inputs"])
            num_outputs = int(data["entangler"]["num_outputs"])
            total_pads = num_inputs + num_outputs
            if total_pads <= 8:
                data["hardware"]["input_pads"] = [f"dio{i}" for i in range(num_inputs)]
                data["hardware"]["output_pads"] = [f"dio{i}" for i in range(num_inputs, total_pads)]
        cfg = ExperimentConfig.model_validate(data)
        cfg.source_path = self.config.source_path
        return cfg

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, text: str, *, content_type: str) -> None:
        data = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _copy_paste_command(cfg: ExperimentConfig) -> str:
    json_path = cfg.output_dir / f"{cfg.target.variant}.json"
    settings_path = cfg.output_dir / "entangler_settings.toml"
    return (
        f"cd {shlex.quote(str(WORKSPACE_ROOT))} && "
        f"./scripts/build_from_json.sh {shlex.quote(display_path(json_path))} "
        f"{shlex.quote(cfg.target.drtio_role)} "
        f"{shlex.quote(display_path(settings_path))} "
        f"{shlex.quote(cfg.repositories.entangler_core_branch)}"
    )


def _job_snapshot() -> dict[str, Any]:
    with _BUILD_LOCK:
        return dict(_BUILD_JOB)


def _set_job(**updates: Any) -> None:
    with _BUILD_LOCK:
        _BUILD_JOB.update(updates)


def _append_job_log(text: str) -> None:
    with _BUILD_LOCK:
        _BUILD_JOB["log"] += text


def _start_build_job(cfg: ExperimentConfig, json_path: Path, settings_path: Path) -> dict[str, Any]:
    try:
        checked_out = checkout_entangler_branch(cfg.repositories.entangler_core_branch)
    except Exception as exc:
        return {"ok": False, "errors": [str(exc)]}

    with _BUILD_LOCK:
        if _BUILD_JOB.get("running"):
            return {"ok": False, "errors": ["A build is already running."]}
        _BUILD_JOB.update(
            {
                "running": True,
                "status": "running",
                "log": (
                    f"Wrote {display_path(json_path)}\n"
                    f"Wrote {display_path(settings_path)}\n"
                    f"Using entangler-core branch: {checked_out}\n"
                ),
                "returncode": None,
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": None,
            }
        )

    thread = threading.Thread(target=_run_build_steps, args=(cfg,), daemon=True)
    thread.start()
    return {"ok": True, "message": "Build started.", "path": display_path(json_path)}


def _run_build_steps(cfg: ExperimentConfig) -> None:
    try:
        for index, command in enumerate(render_build_steps(cfg), start=1):
            _append_job_log(f"\n[{index}] {command}\n")
            process = subprocess.Popen(
                command,
                cwd=WORKSPACE_ROOT,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                _append_job_log(line)
            returncode = process.wait()
            if returncode != 0:
                _append_job_log(f"\nCommand failed with exit code {returncode}.\n")
                _set_job(running=False, status="failed", returncode=returncode, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                return
        _append_job_log(f"\nBuild complete. Firmware: {firmware_name(cfg)}\n")
        _set_job(running=False, status="complete", returncode=0, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as exc:
        _append_job_log(f"\nBuild failed before completion: {exc}\n")
        _set_job(running=False, status="failed", returncode=1, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))


def _custom_job_snapshot() -> dict[str, Any]:
    with _CUSTOM_LOCK:
        return dict(_CUSTOM_JOB)


def _set_custom_job(**updates: Any) -> None:
    with _CUSTOM_LOCK:
        _CUSTOM_JOB.update(updates)


def _append_custom_log(text: str) -> None:
    with _CUSTOM_LOCK:
        _CUSTOM_JOB["log"] += text


def _start_custom_checks(logic_name: str, *, include_nix: bool = False) -> dict[str, Any]:
    commands = verification_commands(logic_name, include_nix=include_nix)
    with _CUSTOM_LOCK:
        if _CUSTOM_JOB.get("running"):
            return {"ok": False, "errors": ["Custom-logic checks are already running."]}
        _CUSTOM_JOB.update(
            {
                "running": True,
                "status": "running",
                "log": "Starting custom-logic verification.\n",
                "returncode": None,
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": None,
            }
        )
    thread = threading.Thread(target=_run_custom_check_steps, args=(commands,), daemon=True)
    thread.start()
    return {"ok": True, "message": "Verification started.", "commands": commands}


def _start_codex_task(spec: dict[str, Any]) -> dict[str, Any]:
    request = write_custom_logic_request(spec)
    prompt = request["prompt"]
    with _CUSTOM_LOCK:
        if _CUSTOM_JOB.get("running"):
            return {"ok": False, "errors": ["A custom-logic job is already running."]}
        _CUSTOM_JOB.update(
            {
                "running": True,
                "status": "running-codex",
                "log": f"Wrote {request['path']}\nStarting Codex for {request['branch']}.\n",
                "returncode": None,
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": None,
            }
        )
    thread = threading.Thread(target=_run_codex_task, args=(prompt,), daemon=True)
    thread.start()
    return {"ok": True, "message": "Codex started.", "request_path": request["path"], "prompt": prompt}


def _run_codex_task(prompt: str) -> None:
    try:
        process = subprocess.Popen(
            [
                "codex",
                "exec",
                "--cd",
                str(WORKSPACE_ROOT),
                "--sandbox",
                "danger-full-access",
                "--dangerously-bypass-approvals-and-sandbox",
                prompt,
            ],
            cwd=WORKSPACE_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            _append_custom_log(line)
        returncode = process.wait()
        status = "complete" if returncode == 0 else "failed"
        _append_custom_log(f"\nCodex finished with exit code {returncode}.\n")
        _set_custom_job(
            running=False,
            status=status,
            returncode=returncode,
            finished_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
    except FileNotFoundError:
        _append_custom_log("\nCodex CLI was not found on PATH.\n")
        _set_custom_job(running=False, status="failed", returncode=127, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as exc:
        _append_custom_log(f"\nCodex failed before completion: {exc}\n")
        _set_custom_job(running=False, status="failed", returncode=1, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))


def _run_custom_check_steps(commands: list[str]) -> None:
    try:
        for index, command in enumerate(commands, start=1):
            _append_custom_log(f"\n[{index}] {command}\n")
            process = run_command_stream(command)
            assert process.stdout is not None
            for line in process.stdout:
                _append_custom_log(line)
            returncode = process.wait()
            if returncode != 0:
                _append_custom_log(f"\nCommand failed with exit code {returncode}.\n")
                _set_custom_job(
                    running=False,
                    status="failed",
                    returncode=returncode,
                    finished_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                )
                return
        _append_custom_log("\nCustom-logic verification complete.\n")
        _set_custom_job(running=False, status="complete", returncode=0, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as exc:
        _append_custom_log(f"\nVerification failed before completion: {exc}\n")
        _set_custom_job(running=False, status="failed", returncode=1, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MADMAX Gateware Mapper</title>
  <meta http-equiv="Cache-Control" content="no-store">
  <style>
    :root {
      --ink: #202124;
      --muted: #5f6368;
      --line: #d8dde3;
      --panel: #ffffff;
      --bg: #f4f6f8;
      --accent: #006d77;
      --warn: #a23b00;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 20px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
    }
    h1 { margin: 0; font-size: 18px; font-weight: 700; }
    .titlebar {
      display: flex;
      align-items: center;
      gap: 18px;
      min-width: 0;
    }
    .view-tabs {
      display: flex;
      gap: 6px;
      align-items: center;
    }
    .view-tabs button {
      padding: 6px 9px;
      font-size: 13px;
    }
    main {
      display: grid;
      grid-template-columns: minmax(520px, 1.1fr) minmax(420px, 0.9fr);
      gap: 16px;
      padding: 16px;
      height: calc(100vh - 58px);
    }
    main[hidden] { display: none; }
    main.custom-workflow {
      grid-template-columns: minmax(520px, 0.95fr) minmax(460px, 1.05fr);
    }
    section {
      min-width: 0;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .section-head {
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .section-head h2 { margin: 0; font-size: 14px; }
    .inline-head {
      border: 1px solid var(--line);
      border-radius: 8px 8px 0 0;
      margin-top: 4px;
      background: #fafbfc;
    }
    .content { padding: 14px; overflow: auto; }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    label { display: grid; gap: 5px; font-size: 12px; color: var(--muted); }
    input, select, textarea, button { font: inherit; }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      background: #ffffff;
      color: var(--ink);
    }
    textarea {
      min-height: 74px;
      resize: vertical;
      font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
    }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 8px;
      text-align: left;
      vertical-align: top;
    }
    th { font-size: 12px; color: var(--muted); font-weight: 650; }
    th:nth-child(1), td:nth-child(1) { width: 26%; }
    th:nth-child(2), td:nth-child(2) { width: 20%; }
    th:nth-child(3), td:nth-child(3) { width: 46%; }
    th:nth-child(4), td:nth-child(4) { width: 8%; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .check-row {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
    }
    .check-row input { width: auto; }
    button {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      background: #ffffff;
      color: var(--ink);
      cursor: pointer;
    }
    button.primary { background: var(--accent); border-color: var(--accent); color: #ffffff; }
    button.active { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
    button.danger { color: var(--warn); }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
      line-height: 1.45;
    }
    .output { flex: 1; min-height: 0; }
    .output pre { min-height: 100%; }
    .status {
      min-height: 32px;
      padding: 8px 14px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
    }
    .state-list {
      display: grid;
      gap: 8px;
      margin-bottom: 14px;
    }
    .hint {
      margin: 8px 0 12px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }
    .state-line {
      display: grid;
      grid-template-columns: 140px minmax(0, 1fr);
      gap: 10px;
      font-size: 12px;
    }
    .state-line strong { color: var(--muted); font-weight: 650; }
    .state-line span {
      overflow-wrap: anywhere;
      font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
    }
    .errors {
      color: var(--warn);
      padding: 8px 14px;
      border-top: 1px solid var(--line);
      font-size: 12px;
    }
    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; height: auto; }
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <header>
    <div class="titlebar">
      <h1>MADMAX Kasli-SoC Gateware Mapper</h1>
      <div class="view-tabs">
        <button id="tab-mapper" class="active">Card Mapper</button>
        <button id="tab-custom">Custom Logic</button>
      </div>
    </div>
    <span id="source"></span>
  </header>
  <main id="mapper-main">
    <section>
      <div class="section-head">
        <h2>Kasli-SoC Configuration</h2>
      </div>
      <div class="content">
        <div class="grid">
          <label>Variant <input id="variant"></label>
          <label>Hardware Rev <input id="hw_rev"></label>
          <label>DRTIO Role <select id="drtio_role"><option>standalone</option><option>master</option><option>satellite</option></select></label>
          <label>RTIO Frequency <input id="rtio_frequency" type="number"></label>
        </div>
        <div class="section-head inline-head">
          <h2>Entangler Logic</h2>
          <div class="actions">
            <button id="add-pattern">Add Pattern</button>
            <button id="all-pattern">All Inputs</button>
          </div>
        </div>
        <div class="grid">
          <label>Entangler Inputs <input id="num_inputs" type="number" min="1" max="8"></label>
          <label>Outputs <input id="num_outputs" type="number" min="1" max="8"></label>
          <label>Generic Inputs <input id="num_generic_inputs" type="number" min="0" max="8"></label>
          <label>Allowed Patterns <input id="num_patterns_allowed" type="number" min="1" max="16"></label>
          <label>Coincidence Window mu <input id="coincidence_window_mu" type="number" min="1"></label>
          <label>Timeout mu <input id="timeout_mu" type="number" min="1"></label>
          <label>Fast Branch <select id="fast_branch"><option value="true">true</option><option value="false">false</option></select></label>
        </div>
        <table>
          <thead>
            <tr><th>Pattern Name</th><th>Required Input Indices</th><th></th></tr>
          </thead>
          <tbody id="pattern-rows"></tbody>
        </table>
        <div class="section-head inline-head">
          <h2>Entangler Core Source</h2>
          <div class="actions">
            <button id="refresh-branches">Refresh Branches</button>
            <button id="checkout-branch">Use Branch</button>
          </div>
        </div>
        <div class="grid">
          <label>Entangler Core Branch <select id="entangler_core_branch"></select></label>
          <label>Current Checkout <input id="current_entangler_branch" readonly></label>
        </div>
        <div class="section-head inline-head">
          <h2>ARTIQ Cards / EEM Connections</h2>
          <div class="actions">
            <button id="add">Add Card</button>
            <button id="entangler">2 In / 2 Out Entangler</button>
            <button id="save" class="primary">Write JSON</button>
          </div>
        </div>
        <p class="hint">An Entangler row owns the DIO EEM port(s) listed in that row. Do not add a separate DIO row for the same EEM port.</p>
        <table>
          <thead>
            <tr><th>Card</th><th>EEM Port(s)</th><th>Options JSON</th><th></th></tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </section>
    <section>
      <div class="section-head">
        <h2>Generated Description</h2>
        <div class="actions">
          <button id="run" class="primary">Run Build</button>
          <button id="copy">Copy Command</button>
          <button id="log">Build Log</button>
          <button id="plan">Build Plan</button>
          <button id="preview" class="active">Preview JSON</button>
        </div>
      </div>
      <div class="output content"><pre id="output"></pre></div>
        <div id="errors" class="errors" hidden></div>
      <div class="status" id="status"></div>
    </section>
  </main>
  <main id="custom-main" class="custom-workflow" hidden>
    <section>
      <div class="section-head">
        <h2>Custom Logic Request</h2>
        <div class="actions">
          <button id="custom-refresh">Refresh</button>
          <button id="custom-write-request">Write Codex Task</button>
          <button id="custom-run-codex" class="primary">Run Codex</button>
          <button id="custom-copy">Copy Prompt</button>
        </div>
      </div>
      <div class="content">
        <div class="grid three">
          <label>Logic Name <input id="custom_logic_name" placeholder="atom photon parity v2"></label>
          <label>Base Branch <select id="custom_base_branch"></select></label>
          <label>Flake Mode
            <select id="custom_flake_mode">
              <option value="local_path">local_path</option>
              <option value="remote_branch">remote_branch</option>
              <option value="none">none</option>
            </select>
          </label>
          <label>Entangler Inputs <input id="custom_num_inputs" type="number" min="1" max="8" value="2"></label>
          <label>Outputs <input id="custom_num_outputs" type="number" min="1" max="8" value="2"></label>
          <label>Target Branch <input id="custom_branch" placeholder="feature/logic-name"></label>
        </div>
        <label>Description <textarea id="custom_description" placeholder="Experiment goal and hardware context"></textarea></label>
        <label>Required Behavior <textarea id="custom_required_behavior" placeholder="Timing-critical behavior Codex should implement"></textarea></label>
        <div class="grid two">
          <label>Inputs <textarea id="custom_inputs" placeholder="SPCM0, SPCM1, reference TTL, ..."></textarea></label>
          <label>Outputs <textarea id="custom_outputs" placeholder="FORT gate, excitation, microwave switch, ..."></textarea></label>
        </div>
        <label>Success / Failure Rules <textarea id="custom_success_failure" placeholder="Success outcomes, retry policy, timeout/failure reasons"></textarea></label>
        <label>Test Experiments <textarea id="custom_test_behavior" placeholder="Smoke, loopback, timing scan, stress, benchmark expectations"></textarea></label>
        <div class="section-head inline-head">
          <h2>Scaffold Options</h2>
          <div class="actions">
            <button id="custom-scaffold" class="primary">Scaffold Workflow</button>
            <button id="custom-wire-flake">Wire Flake</button>
          </div>
        </div>
        <div class="grid three">
          <label class="check-row"><input id="custom_create_branch" type="checkbox" checked> create branch</label>
          <label class="check-row"><input id="custom_scaffold_core" type="checkbox" checked> core files</label>
          <label class="check-row"><input id="custom_scaffold_env" type="checkbox" checked> ARTIQ env</label>
          <label class="check-row"><input id="custom_scaffold_config" type="checkbox" checked> experiment YAML</label>
          <label class="check-row"><input id="custom_include_nix" type="checkbox"> include Nix checks</label>
        </div>
      </div>
      <div class="status" id="custom-status"></div>
    </section>
    <section>
      <div class="section-head">
        <h2>Workflow State</h2>
        <div class="actions">
          <button id="custom-run-checks" class="primary">Run Checks</button>
          <button id="custom-show-prompt">Prompt</button>
          <button id="custom-show-log" class="active">Log</button>
          <button id="custom-show-state">State</button>
        </div>
      </div>
      <div class="content">
        <div class="state-list">
          <div class="state-line"><strong>Entangler branch</strong><span id="custom_state_branch"></span></div>
          <div class="state-line"><strong>Zynq flake input</strong><span id="custom_state_flake"></span></div>
          <div class="state-line"><strong>ARTIQ envs</strong><span id="custom_state_envs"></span></div>
          <div class="state-line"><strong>Codex runner</strong><span id="custom_state_codex"></span></div>
        </div>
      </div>
      <div class="output content"><pre id="custom-output"></pre></div>
      <div class="status" id="custom-log-status"></div>
    </section>
  </main>
  <script>
    let state = null;
    let cards = [];
    let refreshTimer = null;
    let refreshSerial = 0;
    let outputMode = "json";
    let latestDescription = null;
    let latestBuildPlan = [];
    let latestBuildLog = "";
    let pollTimer = null;
    let customState = null;
    let latestCustomPrompt = "";
    let latestCustomLog = "";
    let customOutputMode = "log";
    let customPollTimer = null;
    const $ = (id) => document.getElementById(id);

    async function api(path, options = {}) {
      const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
      const text = await response.text();
      let data = {};
      if (text) {
        try {
          data = JSON.parse(text);
        } catch (error) {
          data = {errors: [text]};
        }
      }
      if (!response.ok) throw data;
      return data;
    }

    function errorMessages(error) {
      if (error && Array.isArray(error.errors)) return error.errors;
      if (error && error.message) return [error.message];
      if (typeof error === "string") return [error];
      return [JSON.stringify(error)];
    }

    function showMapperError(prefix, error) {
      const messages = errorMessages(error);
      $("errors").hidden = false;
      $("errors").textContent = messages.map((message) => `- ${message}`).join("\n");
      latestBuildLog = `${prefix}\n${messages.join("\n")}`;
      setOutputMode("log");
      setStatus(prefix);
    }

    function showCustomError(prefix, error) {
      const messages = errorMessages(error);
      latestCustomLog = `${prefix}\n${messages.join("\n")}`;
      setCustomOutputMode("log");
      setCustomStatus(prefix);
      setCustomLogStatus(prefix);
    }

    function target() {
      return {
        variant: $("variant").value,
        hw_rev: $("hw_rev").value,
        drtio_role: $("drtio_role").value,
        rtio_frequency: Number($("rtio_frequency").value)
      };
    }

    function entanglerLogic() {
      return {
        num_inputs: Number($("num_inputs").value),
        num_outputs: Number($("num_outputs").value),
        num_generic_inputs: Number($("num_generic_inputs").value),
        num_patterns_allowed: Number($("num_patterns_allowed").value),
        coincidence_window_mu: Number($("coincidence_window_mu").value),
        timeout_mu: Number($("timeout_mu").value),
        fast_branch: $("fast_branch").value === "true",
        input_names: Array.from({length: Number($("num_inputs").value)}, (_, index) => `input${index}`),
        output_names: Array.from({length: Number($("num_outputs").value)}, (_, index) => `output${index}`),
        patterns: collectPatterns().patterns
      };
    }

    function repositories() {
      return {
        entangler_core_branch: $("entangler_core_branch").value
      };
    }

    function collectPatterns() {
      const patterns = [];
      const errors = [];
      [...$("pattern-rows").querySelectorAll("tr")].forEach((row, index) => {
        const name = row.querySelector("[data-pattern-name]").value.trim() || `pattern_${index}`;
        const inputsText = row.querySelector("[data-pattern-inputs]").value.trim();
        const inputs = [];
        if (inputsText) {
          for (const part of inputsText.split(",")) {
            const value = Number(part.trim());
            if (!Number.isInteger(value)) {
              errors.push(`Pattern ${index + 1}: input indices must be comma-separated integers`);
            } else {
              inputs.push(value);
            }
          }
        }
        patterns.push({name, inputs});
      });
      return {patterns, errors};
    }

    function localDescription(peripherals) {
      const currentTarget = target();
      return {
        target: state.config.target.board,
        variant: currentTarget.variant,
        hw_rev: currentTarget.hw_rev,
        drtio_role: currentTarget.drtio_role,
        rtio_frequency: currentTarget.rtio_frequency,
        peripherals: peripherals
      };
    }

    function collectRows() {
      const peripherals = [];
      const errors = [];
      [...$("rows").querySelectorAll("tr")].forEach((row, index) => {
        const card = row.querySelector("[data-card]").value;
        const definition = cards.find((item) => item.type === card);
        if (!definition) {
          errors.push(`Row ${index + 1}: unknown card type ${card}`);
          return;
        }
        const portsText = row.querySelector("[data-ports]").value.trim();
        const ports = [];
        if (portsText) {
          for (const part of portsText.split(",")) {
            const value = Number(part.trim());
            if (!Number.isInteger(value)) {
              errors.push(`Row ${index + 1}: EEM ports must be comma-separated integers`);
            } else {
              ports.push(value);
            }
          }
        }
        const optionsText = row.querySelector("[data-options]").value.trim();
        let options = {};
        if (optionsText) {
          try {
            options = JSON.parse(optionsText);
          } catch (error) {
            errors.push(`Row ${index + 1}: options JSON is not valid`);
          }
        }
        const peripheral = {type: card, ...options};
        if (definition.port_count !== 0 || definition.min_ports !== null) peripheral.ports = ports;
        peripherals.push(peripheral);
      });
      return {peripherals, errors};
    }

    function addPatternRow(pattern = {name: "both_inputs", inputs: [0, 1]}) {
      const row = document.createElement("tr");
      const nameCell = document.createElement("td");
      const inputsCell = document.createElement("td");
      const removeCell = document.createElement("td");
      const name = document.createElement("input");
      name.dataset.patternName = "true";
      name.value = pattern.name || "pattern";
      const inputs = document.createElement("input");
      inputs.dataset.patternInputs = "true";
      inputs.value = pattern.inputs ? pattern.inputs.join(",") : "";
      const remove = document.createElement("button");
      remove.textContent = "X";
      remove.className = "danger";
      name.addEventListener("input", scheduleRefresh);
      inputs.addEventListener("input", scheduleRefresh);
      remove.addEventListener("click", () => {
        row.remove();
        scheduleRefresh();
      });
      nameCell.appendChild(name);
      inputsCell.appendChild(inputs);
      removeCell.appendChild(remove);
      row.append(nameCell, inputsCell, removeCell);
      $("pattern-rows").appendChild(row);
      scheduleRefresh();
    }

    function setStatus(text) {
      $("status").textContent = text;
    }

    function setOutputMode(mode) {
      outputMode = mode;
      $("preview").classList.toggle("active", mode === "json");
      $("plan").classList.toggle("active", mode === "plan");
      $("log").classList.toggle("active", mode === "log");
      renderOutput();
    }

    function renderOutput() {
      if (outputMode === "log") {
        $("output").textContent = latestBuildLog || "No build has been started yet.";
        scrollOutputToBottom();
      } else if (outputMode === "plan") {
        $("output").textContent = latestBuildPlan.length ? latestBuildPlan.join("\n") : "Build plan is not available yet.";
      } else {
        $("output").textContent = latestDescription ? JSON.stringify(latestDescription, null, 2) : "";
      }
    }

    function scrollOutputToBottom() {
      const output = $("output");
      const container = output.closest(".output");
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    }

    function logicModeForBranch(branch) {
      let branchName = (branch || "").trim();
      if (branchName.startsWith("origin/")) branchName = branchName.slice("origin/".length);
      if (["", "master", "main", "artiq-integration"].includes(branchName)) return "legacy";
      if (branchName.startsWith("feature/")) branchName = branchName.slice("feature/".length);
      return branchName.replace(/[-/]+/g, "_");
    }

    function defaultOptionsForCard(cardType) {
      const definition = cards.find((item) => item.type === cardType);
      const defaults = definition ? {...definition.default_options} : {};
      if (cardType === "entangler") {
        delete defaults.logic_mode;
        const logicMode = logicModeForBranch($("entangler_core_branch").value);
        if (logicMode !== "legacy") defaults.logic_mode = logicMode;
      }
      return defaults;
    }

    function parseOptions(text) {
      if (!text.trim()) return {};
      try {
        return JSON.parse(text);
      } catch (error) {
        return null;
      }
    }

    function applyEntanglerBranchDefaultsToRows() {
      const defaults = defaultOptionsForCard("entangler");
      for (const row of $("rows").querySelectorAll("tr")) {
        const select = row.querySelector("[data-card]");
        const options = row.querySelector("[data-options]");
        if (!select || !options || select.value !== "entangler") continue;
        const current = parseOptions(options.value);
        if (current === null) continue;
        const next = {...current, ...defaults};
        if (!Object.prototype.hasOwnProperty.call(defaults, "logic_mode")) {
          delete next.logic_mode;
        }
        options.value = JSON.stringify(next, null, 2);
      }
    }

    function defaultEntanglerPeripheral() {
      return {
        type: "entangler",
        ports: [state.config.hardware.dio_eem],
        ...defaultOptionsForCard("entangler")
      };
    }

    function cardSelect(value) {
      const select = document.createElement("select");
      select.dataset.card = "true";
      for (const card of cards) {
        const option = document.createElement("option");
        option.value = card.type;
        option.textContent = card.label;
        select.appendChild(option);
      }
      select.value = value;
      return select;
    }

    function addRow(peripheral = {type: "dio", ports: [0]}) {
      const definition = cards.find((item) => item.type === peripheral.type) || cards[0];
      const row = document.createElement("tr");
      const cardCell = document.createElement("td");
      const portsCell = document.createElement("td");
      const optionsCell = document.createElement("td");
      const removeCell = document.createElement("td");
      const select = cardSelect(definition.type);
      const ports = document.createElement("input");
      ports.dataset.ports = "true";
      ports.value = peripheral.ports ? peripheral.ports.join(",") : "";
      const options = document.createElement("textarea");
      options.dataset.options = "true";
      const optionCopy = {...peripheral};
      delete optionCopy.type;
      delete optionCopy.ports;
      options.value = JSON.stringify(optionCopy, null, 2);
      const remove = document.createElement("button");
      remove.textContent = "X";
      remove.className = "danger";

      function applyDefinition() {
        const def = cards.find((item) => item.type === select.value);
        if (def.port_count === 0) {
          if (def.min_ports === null) {
            ports.value = "";
          } else if (!ports.value.trim()) {
            ports.value = "0";
          }
        } else {
          const existing = ports.value.trim() ? Number(ports.value.split(",")[0].trim()) : 0;
          const startPort = Number.isInteger(existing) ? existing : 0;
            ports.value = Array.from({length: def.port_count}, (_, index) => startPort + index).join(",");
        }
        options.value = JSON.stringify(defaultOptionsForCard(def.type), null, 2);
        scheduleRefresh();
      }

      select.addEventListener("change", applyDefinition);
      ports.addEventListener("input", scheduleRefresh);
      options.addEventListener("input", scheduleRefresh);
      remove.addEventListener("click", () => {
        row.remove();
        scheduleRefresh();
      });
      cardCell.appendChild(select);
      portsCell.appendChild(ports);
      optionsCell.appendChild(options);
      removeCell.appendChild(remove);
      row.append(cardCell, portsCell, optionsCell, removeCell);
      $("rows").appendChild(row);
      scheduleRefresh();
    }

    function scheduleRefresh() {
      clearTimeout(refreshTimer);
      refreshTimer = setTimeout(refresh, 80);
    }

    async function refresh() {
      const serial = ++refreshSerial;
      const rowState = collectRows();
      const patternState = collectPatterns();
      latestDescription = localDescription(rowState.peripherals);
      renderOutput();
      try {
        const data = await api("/api/preview", {
          method: "POST",
          body: JSON.stringify({target: target(), repositories: repositories(), entangler: entanglerLogic(), peripherals: rowState.peripherals})
        });
        if (serial !== refreshSerial) return;
        latestDescription = data.description;
        latestBuildPlan = data.build_plan;
        renderOutput();
        const errors = [...rowState.errors, ...patternState.errors, ...data.errors];
        if (errors.length) {
          $("errors").hidden = false;
          $("errors").textContent = errors.map((error) => `- ${error}`).join("\n");
        } else {
          $("errors").hidden = true;
          $("errors").textContent = "";
        }
        setStatus("Preview is current.");
      } catch (error) {
        if (serial !== refreshSerial) return;
        const messages = error && error.errors ? error.errors : [error && error.message ? error.message : JSON.stringify(error)];
        const errors = [...rowState.errors, ...patternState.errors, ...messages];
        $("errors").hidden = false;
        $("errors").textContent = errors.map((message) => `- ${message}`).join("\n");
        latestBuildPlan = [];
        renderOutput();
        setStatus("Preview updated locally; server validation has errors.");
      }
    }

    async function saveJson() {
      try {
        const rowState = collectRows();
        const patternState = collectPatterns();
        if (rowState.errors.length || patternState.errors.length) {
          $("errors").hidden = false;
          $("errors").textContent = [...rowState.errors, ...patternState.errors].map((error) => `- ${error}`).join("\n");
          setStatus("Fix row errors before writing JSON.");
          return;
        }
        const data = await api("/api/save-json", {
          method: "POST",
          body: JSON.stringify({target: target(), repositories: repositories(), entangler: entanglerLogic(), peripherals: rowState.peripherals})
        });
        setStatus(`Wrote ${data.path} and ${data.settings_path}`);
      } catch (error) {
        showMapperError("Write JSON failed.", error);
      }
    }

    async function copyCommand() {
      try {
        const rowState = collectRows();
        const patternState = collectPatterns();
        if (rowState.errors.length || patternState.errors.length) {
          $("errors").hidden = false;
          $("errors").textContent = [...rowState.errors, ...patternState.errors].map((error) => `- ${error}`).join("\n");
          setStatus("Fix row errors before copying the command.");
          return;
        }
        const data = await api("/api/copy-command", {
          method: "POST",
          body: JSON.stringify({target: target(), repositories: repositories(), entangler: entanglerLogic(), peripherals: rowState.peripherals})
        });
        latestBuildLog = data.command;
        setOutputMode("log");
        try {
          await navigator.clipboard.writeText(data.command);
          setStatus(`Copied command. Wrote ${data.path} and ${data.settings_path}`);
        } catch (error) {
          setStatus(`Command is shown above. Wrote ${data.path} and ${data.settings_path}`);
        }
      } catch (error) {
        showMapperError("Copy command failed.", error);
      }
    }

    async function runBuild() {
      try {
        const rowState = collectRows();
        const patternState = collectPatterns();
        if (rowState.errors.length || patternState.errors.length) {
          $("errors").hidden = false;
          $("errors").textContent = [...rowState.errors, ...patternState.errors].map((error) => `- ${error}`).join("\n");
          setStatus("Fix row errors before running the build.");
          return;
        }
        const data = await api("/api/run-build", {
          method: "POST",
          body: JSON.stringify({target: target(), repositories: repositories(), entangler: entanglerLogic(), peripherals: rowState.peripherals})
        });
        latestBuildLog = data.message || "Build started.";
        setOutputMode("log");
        setStatus(`${data.message} Wrote ${data.path}`);
        startPollingBuild();
      } catch (error) {
        showMapperError("Run build failed.", error);
      }
    }

    async function pollBuildStatus() {
      const data = await api("/api/build-status");
      latestBuildLog = data.log || "";
      if (outputMode === "log") renderOutput();
      setStatus(`Build status: ${data.status}`);
      if (!data.running) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }

    function startPollingBuild() {
      clearInterval(pollTimer);
      pollBuildStatus();
      pollTimer = setInterval(pollBuildStatus, 1200);
    }

    async function loadEntanglerBranches(options = {}) {
      try {
        const data = await api("/api/entangler-branches");
        const select = $("entangler_core_branch");
        const previous = select.value;
        select.innerHTML = "";
        for (const branch of data.branches) {
          const option = document.createElement("option");
          option.value = branch;
          option.textContent = branch;
          select.appendChild(option);
        }
        let preferred = data.current || state.config.repositories.entangler_core_branch || data.selected;
        if (options.preferCurrent) {
          preferred = data.current || preferred;
        } else if (previous && data.branches.includes(previous)) {
          preferred = previous;
        }
        if (preferred && data.branches.includes(preferred)) {
          select.value = preferred;
        }
        $("current_entangler_branch").value = data.current;
        applyEntanglerBranchDefaultsToRows();
        scheduleRefresh();
      } catch (error) {
        showMapperError("Branch refresh failed.", error);
      }
    }

    async function checkoutSelectedBranch() {
      try {
        const data = await api("/api/checkout-entangler", {
          method: "POST",
          body: JSON.stringify({branch: $("entangler_core_branch").value})
        });
        $("current_entangler_branch").value = data.current;
        applyEntanglerBranchDefaultsToRows();
        setStatus(`Entangler core branch is now ${data.current}`);
        await loadEntanglerBranches({preferCurrent: true});
      } catch (error) {
        showMapperError("Branch checkout failed.", error);
      }
    }

    function showView(name) {
      const custom = name === "custom";
      $("mapper-main").hidden = custom;
      $("custom-main").hidden = !custom;
      $("tab-mapper").classList.toggle("active", !custom);
      $("tab-custom").classList.toggle("active", custom);
      if (custom) loadCustomState();
      else loadEntanglerBranches({preferCurrent: true});
    }

    function customSpec() {
      const name = $("custom_logic_name").value.trim();
      const autoBranch = name ? `feature/${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}` : "";
      return {
        logic_name: name,
        base_branch: $("custom_base_branch").value || "artiq-integration",
        branch: $("custom_branch").value.trim() || autoBranch,
        flake_mode: $("custom_flake_mode").value,
        num_inputs: Number($("custom_num_inputs").value || 2),
        num_outputs: Number($("custom_num_outputs").value || 2),
        description: $("custom_description").value,
        required_behavior: $("custom_required_behavior").value,
        inputs: $("custom_inputs").value,
        outputs: $("custom_outputs").value,
        success_failure_rules: $("custom_success_failure").value,
        test_behavior: $("custom_test_behavior").value,
        create_branch: $("custom_create_branch").checked,
        scaffold_core: $("custom_scaffold_core").checked,
        scaffold_env: $("custom_scaffold_env").checked,
        scaffold_config: $("custom_scaffold_config").checked
      };
    }

    function setCustomStatus(text) {
      $("custom-status").textContent = text;
    }

    function setCustomLogStatus(text) {
      $("custom-log-status").textContent = text;
    }

    function renderCustomOutput() {
      if (customOutputMode === "prompt") {
        $("custom-output").textContent = latestCustomPrompt || "No Codex task has been written yet.";
      } else if (customOutputMode === "state") {
        $("custom-output").textContent = customState ? JSON.stringify(customState, null, 2) : "State is not loaded yet.";
      } else {
        $("custom-output").textContent = latestCustomLog || "No custom-logic workflow action has run yet.";
        const container = $("custom-output").closest(".output");
        if (container) container.scrollTop = container.scrollHeight;
      }
      $("custom-show-prompt").classList.toggle("active", customOutputMode === "prompt");
      $("custom-show-log").classList.toggle("active", customOutputMode === "log");
      $("custom-show-state").classList.toggle("active", customOutputMode === "state");
    }

    function setCustomOutputMode(mode) {
      customOutputMode = mode;
      renderCustomOutput();
    }

    async function loadCustomState() {
      customState = await api("/api/custom-logic/state");
      const branchSelect = $("custom_base_branch");
      const previous = branchSelect.value || customState.current_branch || "artiq-integration";
      branchSelect.innerHTML = "";
      for (const branch of customState.branches) {
        const option = document.createElement("option");
        option.value = branch;
        option.textContent = branch;
        branchSelect.appendChild(option);
      }
      if (customState.branches.includes(previous)) branchSelect.value = previous;
      $("custom_state_branch").textContent = customState.current_branch || "unknown";
      $("custom_state_flake").textContent = customState.flake_entangler_url || "not found";
      $("custom_state_envs").textContent = customState.artiq_envs.join(", ") || "none";
      $("custom_state_codex").textContent = customState.codex_available ? "available" : "task file handoff";
      if (!customOutputMode || customOutputMode === "state") renderCustomOutput();
    }

    async function writeCustomRequest() {
      try {
        const data = await api("/api/custom-logic/request", {
          method: "POST",
          body: JSON.stringify(customSpec())
        });
        latestCustomPrompt = data.prompt;
        latestCustomLog = `Wrote ${data.path}\nTarget branch: ${data.branch}`;
        setCustomOutputMode("prompt");
        setCustomStatus(`Wrote ${data.path}`);
        await loadCustomState();
      } catch (error) {
        showCustomError("Write Codex task failed.", error);
      }
    }

    async function scaffoldCustomWorkflow() {
      try {
        const data = await api("/api/custom-logic/scaffold", {
          method: "POST",
          body: JSON.stringify(customSpec())
        });
        latestCustomPrompt = data.prompt;
        latestCustomLog = `${data.log}\n\nPaths:\n${data.paths.map((path) => `- ${path}`).join("\n")}`;
        setCustomOutputMode("log");
        setCustomStatus(`Scaffolded ${data.slug} on ${data.branch}`);
        await loadCustomState();
        await loadEntanglerBranches({preferCurrent: true});
      } catch (error) {
        showCustomError("Scaffold failed.", error);
      }
    }

    async function wireCustomFlake() {
      try {
        const spec = customSpec();
        const data = await api("/api/custom-logic/update-flake", {
          method: "POST",
          body: JSON.stringify({flake_mode: spec.flake_mode === "none" ? "local_path" : spec.flake_mode, branch: spec.branch})
        });
        latestCustomLog = `Updated ${data.path}\n${data.url}`;
        setCustomOutputMode("log");
        setCustomStatus(`Flake input is ${data.url}`);
        await loadCustomState();
      } catch (error) {
        showCustomError("Flake wiring failed.", error);
      }
    }

    async function copyCustomPrompt() {
      if (!latestCustomPrompt) await writeCustomRequest();
      try {
        await navigator.clipboard.writeText(latestCustomPrompt);
        setCustomStatus("Copied Codex task prompt.");
      } catch (error) {
        setCustomOutputMode("prompt");
        setCustomStatus("Prompt is shown in the output pane.");
      }
    }

    async function runCodexTask() {
      try {
        const data = await api("/api/custom-logic/run-codex", {
          method: "POST",
          body: JSON.stringify(customSpec())
        });
        latestCustomPrompt = data.prompt;
        latestCustomLog = `${data.message}\n${data.request_path}`;
        setCustomOutputMode("log");
        setCustomLogStatus("Codex running.");
        startPollingCustomChecks();
      } catch (error) {
        showCustomError("Run Codex failed.", error);
      }
    }

    async function runCustomChecks() {
      try {
        const spec = customSpec();
        const data = await api("/api/custom-logic/run-checks", {
          method: "POST",
          body: JSON.stringify({logic_name: spec.logic_name, include_nix: $("custom_include_nix").checked})
        });
        latestCustomLog = `${data.message}\n\n${data.commands.join("\n")}`;
        setCustomOutputMode("log");
        setCustomLogStatus("Verification running.");
        startPollingCustomChecks();
      } catch (error) {
        showCustomError("Run checks failed.", error);
      }
    }

    async function pollCustomChecks() {
      const data = await api("/api/custom-logic/job-status");
      latestCustomLog = data.log || "";
      if (customOutputMode === "log") renderCustomOutput();
      setCustomLogStatus(`Verification status: ${data.status}`);
      if (!data.running) {
        clearInterval(customPollTimer);
        customPollTimer = null;
        loadCustomState();
        loadEntanglerBranches({preferCurrent: true});
      }
    }

    function startPollingCustomChecks() {
      clearInterval(customPollTimer);
      pollCustomChecks();
      customPollTimer = setInterval(pollCustomChecks, 1200);
    }

    async function init() {
      state = await api("/api/state");
      cards = state.cards;
      $("source").textContent = state.source || "";
      $("variant").value = state.config.target.variant;
      $("hw_rev").value = state.config.target.hw_rev;
      $("drtio_role").value = state.config.target.drtio_role;
      $("rtio_frequency").value = state.config.target.rtio_frequency;
      $("num_inputs").value = state.config.entangler.num_inputs;
      $("num_outputs").value = state.config.entangler.num_outputs;
      $("num_generic_inputs").value = state.config.entangler.num_generic_inputs;
      $("num_patterns_allowed").value = state.config.entangler.num_patterns_allowed;
      $("coincidence_window_mu").value = state.config.entangler.coincidence_window_mu;
      $("timeout_mu").value = state.config.entangler.timeout_mu;
      $("fast_branch").value = String(state.config.entangler.fast_branch);
      await loadEntanglerBranches({preferCurrent: true});
      for (const pattern of state.config.entangler.patterns) addPatternRow(pattern);
      for (const peripheral of state.peripherals) addRow(peripheral);
      applyEntanglerBranchDefaultsToRows();
      $("add").addEventListener("click", () => addRow());
      $("add-pattern").addEventListener("click", () => addPatternRow({name: `pattern_${$("pattern-rows").children.length}`, inputs: []}));
      $("all-pattern").addEventListener("click", () => {
        $("pattern-rows").innerHTML = "";
        const numInputs = Number($("num_inputs").value);
        addPatternRow({name: "all_inputs", inputs: Array.from({length: numInputs}, (_, index) => index)});
      });
      $("entangler").addEventListener("click", () => {
        $("rows").innerHTML = "";
        addRow(defaultEntanglerPeripheral());
      });
      $("save").addEventListener("click", saveJson);
      $("refresh-branches").addEventListener("click", () => loadEntanglerBranches({preferCurrent: true}));
      $("checkout-branch").addEventListener("click", checkoutSelectedBranch);
      $("copy").addEventListener("click", copyCommand);
      $("run").addEventListener("click", runBuild);
      $("log").addEventListener("click", () => setOutputMode("log"));
      $("preview").addEventListener("click", () => setOutputMode("json"));
      $("plan").addEventListener("click", () => setOutputMode("plan"));
      $("tab-mapper").addEventListener("click", () => showView("mapper"));
      $("tab-custom").addEventListener("click", () => showView("custom"));
      $("custom-refresh").addEventListener("click", loadCustomState);
      $("custom-write-request").addEventListener("click", writeCustomRequest);
      $("custom-run-codex").addEventListener("click", runCodexTask);
      $("custom-copy").addEventListener("click", copyCustomPrompt);
      $("custom-scaffold").addEventListener("click", scaffoldCustomWorkflow);
      $("custom-wire-flake").addEventListener("click", wireCustomFlake);
      $("custom-run-checks").addEventListener("click", runCustomChecks);
      $("custom-show-prompt").addEventListener("click", () => setCustomOutputMode("prompt"));
      $("custom-show-log").addEventListener("click", () => setCustomOutputMode("log"));
      $("custom-show-state").addEventListener("click", () => setCustomOutputMode("state"));
      for (const id of ["variant", "hw_rev", "drtio_role", "rtio_frequency", "num_inputs", "num_outputs", "num_generic_inputs", "num_patterns_allowed", "coincidence_window_mu", "timeout_mu", "fast_branch"]) {
        $(id).addEventListener("input", scheduleRefresh);
      }
      $("entangler_core_branch").addEventListener("input", () => {
        applyEntanglerBranchDefaultsToRows();
        scheduleRefresh();
      });
      $("custom_logic_name").addEventListener("input", () => {
        const name = $("custom_logic_name").value.trim();
        if (!$("custom_branch").value.trim() && name) {
          $("custom_branch").placeholder = `feature/${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`;
        }
      });
      refresh();
      loadCustomState();
    }

    init().catch((error) => {
      $("output").textContent = String(error);
    });
  </script>
</body>
</html>
"""
