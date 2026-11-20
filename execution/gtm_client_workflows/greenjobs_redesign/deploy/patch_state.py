"""Shared writer for the patch-status JSON the monthly report reads (no network).

description: merge one section ("audit" or "compat") into patches.json atomically. null = not measured.
inputs: path, section name, dict
outputs: the JSON file (default <state>/inputs/patches.json)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT = (
    Path(__file__).resolve().parents[4]
    / ".tmp"
    / "greenjobs_ops"
    / "inputs"
    / "patches.json"
)


def merge_write(path: Path, section: str, value: dict[str, Any]) -> dict[str, Any]:
    try:
        cur = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(cur, dict):
            cur = {}
    except (FileNotFoundError, ValueError):
        cur = {}
    cur[section] = value
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(cur, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return cur
