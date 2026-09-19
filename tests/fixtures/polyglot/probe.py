"""Python's half of the probe tree: a way in, a boundary, a loop and a branch."""

from __future__ import annotations

import os
from pathlib import Path

RETRIES = 3


def load_config(path: Path) -> dict[str, str]:
    """Read a config file, one line at a time."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def main() -> int:
    root = os.environ.get("PROBE_ROOT", ".")
    config = load_config(Path(root) / "probe.cfg")
    print(f"{len(config)} settings")
    return 0
