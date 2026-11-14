"""What the code and data looked like: git commit and DVC hashes (INSTRUCTIONS 17.2)."""

import subprocess
from pathlib import Path

import yaml


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def dvc_hash(pointer: Path) -> str | None:
    """md5 recorded in a DVC pointer file such as data.dvc, or None."""
    if not pointer.is_file():
        return None
    outs = (yaml.safe_load(pointer.read_text()) or {}).get("outs", [])
    return outs[0].get("md5") if outs else None
