#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "repos/madmax-artiq-zynq/kasli-soc-standalone_node1_with_edgecounters_en.json"
DEFAULT_OUTPUT_DIR = ROOT / "gateware_build/descriptions/node1_incremental"
DEFAULT_ARTIFACT_DIR = ROOT / "gateware_build/artifacts/node1_incremental"
BUILD_SCRIPT = ROOT / "gateware_build/scripts/build_from_json.sh"
ZYNQ = ROOT / "repos/madmax-artiq-zynq"


def card_label(peripheral: dict) -> str:
    ports = "_".join(str(port) for port in peripheral.get("ports", []))
    return f"eem{ports}_{peripheral['type']}"


def variant_name(index: int, peripherals: list[dict]) -> str:
    last = card_label(peripherals[-1])
    return f"{index:02d}_through_{last}.json"


def write_description(source: dict, peripherals: list[dict], output: Path) -> None:
    description = {
        key: value
        for key, value in source.items()
        if key != "peripherals"
    }
    description["peripherals"] = peripherals
    output.write_text(json.dumps(description, indent=4) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_variant(path: Path, artifact_root: Path) -> Path:
    artifact_dir = artifact_root / path.stem
    artifact_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ZYNQ / "build/boot.bin", artifact_dir / "boot.bin")
    shutil.copy2(ZYNQ / "device_db.py", artifact_dir / "device_db.py")
    shutil.copy2(path, artifact_dir / path.name)
    (artifact_dir / "SHA256SUMS").write_text(
        f"{sha256(artifact_dir / 'boot.bin')}  boot.bin\n",
        encoding="utf-8",
    )
    return artifact_dir


def build_variant(path: Path, role: str, artifact_root: Path) -> Path:
    subprocess.run([str(BUILD_SCRIPT), str(path), role], cwd=ROOT, check=True)
    return package_variant(path, artifact_root)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate cumulative native Node 1 JSON descriptions for one-card-at-a-time EEM diagnosis."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--role", default="standalone", choices=["standalone", "master", "satellite"])
    parser.add_argument("--build", action="store_true", help="Build and package each generated JSON after writing it.")
    parser.add_argument("--only", type=int, help="Generate/build only the Nth cumulative variant, starting at 1.")
    args = parser.parse_args()

    source_path = args.source.resolve()
    output_dir = args.output_dir.resolve()
    artifact_root = args.artifact_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    source = json.loads(source_path.read_text(encoding="utf-8"))
    peripherals = source["peripherals"]

    commands = [
        "# Node 1 Incremental Native Build Commands",
        "",
        "Each command builds a native, non-entangler Kasli-SoC image from a cumulative card list.",
        "Copy `repos/madmax-artiq-zynq/build/boot.bin` after each successful build before starting the next one.",
        "To build and package one variant automatically, run the generator with `--build --only N`.",
        "",
    ]

    for index in range(1, len(peripherals) + 1):
        if args.only is not None and index != args.only:
            continue

        selected = peripherals[:index]
        output = output_dir / variant_name(index, selected)
        write_description(source, selected, output)

        rel_output = output.relative_to(ROOT)
        command = f"./gateware_build/scripts/build_from_json.sh {rel_output} {args.role}"
        commands.extend([f"## {output.name}", "", "```bash", command, "```", ""])
        print(f"Wrote {rel_output}")

        if args.build:
            artifact_dir = build_variant(output, args.role, artifact_root)
            print(f"Packaged {artifact_dir.relative_to(ROOT)}")

    (output_dir / "BUILD_COMMANDS.md").write_text("\n".join(commands) + "\n", encoding="utf-8")
    print(f"Wrote {(output_dir / 'BUILD_COMMANDS.md').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
