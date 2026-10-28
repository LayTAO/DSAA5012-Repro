#!/usr/bin/env python3
"""Record runtime and build metadata without collecting login details."""

import argparse
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def command(argv, cwd=None):
    if shutil.which(argv[0]) is None:
        return {"available": False}
    try:
        result = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=15
        )
        return {
            "available": True,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"available": True, "error": str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "environment.json")
    args = parser.parse_args()
    lock = json.loads((ROOT / "configs" / "upstream.lock.json").read_text())
    snapshot = {
        "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "system": platform.system(),
        "release": platform.release(),
        "architecture": platform.machine(),
        "logical_cpu_count": os.cpu_count(),
        "python": sys.version,
        "upstream_lock": lock,
        "tools": {
            name: command([name, "--version"])
            for name in ["git", "g++", "cmake"]
        },
        "project_commit": command(["git", "rev-parse", "HEAD"], cwd=ROOT),
        "upstream_checkouts": {},
    }
    for repository in lock["repositories"]:
        checkout = ROOT / "external" / repository["name"]
        if (checkout / ".git").is_dir():
            snapshot["upstream_checkouts"][repository["name"]] = {
                "commit": command(["git", "rev-parse", "HEAD"], cwd=checkout),
                "status": command(["git", "status", "--porcelain"], cwd=checkout),
            }
    if platform.system() == "Linux":
        snapshot["cpu"] = command(["lscpu"])
        snapshot["memory"] = command(["free", "-b"])
    elif platform.system() == "Darwin":
        snapshot["cpu"] = command(["sysctl", "-n", "machdep.cpu.brand_string"])
        snapshot["physical_cpu_count"] = command(["sysctl", "-n", "hw.physicalcpu"])
        snapshot["memory_bytes"] = command(["sysctl", "-n", "hw.memsize"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")
    print("Environment written to " + str(args.output))


if __name__ == "__main__":
    main()
