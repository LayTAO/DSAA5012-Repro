#!/usr/bin/env python3
"""Fetch author repositories at pinned commits without running their code."""

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git(*args, cwd=None, capture=False):
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else None


def fetch(repository):
    name, commit, url = (
        repository["name"], repository["commit"], repository["url"]
    )
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
        raise ValueError("Invalid repository directory name")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("A full commit SHA is required for " + name)
    if not url.startswith("https://github.com/"):
        raise ValueError("Expected an HTTPS GitHub source for " + name)

    destination = ROOT / "external" / name
    if destination.exists():
        if not (destination / ".git").is_dir():
            raise RuntimeError(str(destination) + " exists but is not a Git checkout")
        actual = git("rev-parse", "HEAD", cwd=destination, capture=True)
        origin = git("remote", "get-url", "origin", cwd=destination, capture=True)
        changes = git("status", "--porcelain", cwd=destination, capture=True)
        if actual != commit or origin != url or changes:
            raise RuntimeError(
                name + " is modified or differs from the lock file; left unchanged"
            )
        print(name + ": already at " + commit, flush=True)
        return

    destination.mkdir(parents=True)
    git("init", "--quiet", str(destination))
    git("remote", "add", "origin", url, cwd=destination)
    git("fetch", "--depth=1", "origin", commit, cwd=destination)
    git("checkout", "--detach", "FETCH_HEAD", cwd=destination)
    actual = git("rev-parse", "HEAD", cwd=destination, capture=True)
    if actual != commit:
        raise RuntimeError("Commit verification failed for " + name)
    print(name + ": pinned to " + actual, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if shutil.which("git") is None:
        raise SystemExit("Git is required")
    lock = json.loads((ROOT / "configs" / "upstream.lock.json").read_text())
    if lock["schema_version"] != 1:
        raise SystemExit("Unsupported lock file version")
    for repository in lock["repositories"]:
        fetch(repository)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(
            str(error) + "\nNo existing checkout was overwritten. "
            "Inspect any incomplete download directory before retrying."
        )
