#!/usr/bin/env python3
"""Parity check: .claude/hooks/jev-router.sh vs the exact argv jev-router-mod runs.

For each prompt in tests/mods/jev-samples.json, feed the same hook JSON to both and compare stdout.
Usage: python3 tests/mods/jev_router_parity.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOD_ARGV = ["python3", "execution/infrastructure/jev_router.py", "hook"]  # = ARGV in hooks/register.tsx
SHELL_ARGV = ["bash", ".claude/hooks/jev-router.sh"]
TIMEOUT_S = 10


def run(argv: list[str], stdin: str) -> str:
    try:
        r = subprocess.run(argv, input=stdin, capture_output=True, text=True, cwd=ROOT, timeout=TIMEOUT_S * 3)
    except subprocess.TimeoutExpired:
        return ""
    return r.stdout if r.returncode == 0 else ""


def mod_context(stdout: str) -> str | None:
    """What the mod attaches: additionalContext, or None (pass-through)."""
    try:
        ctx = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        return ctx if isinstance(ctx, str) and ctx else None
    except (ValueError, KeyError, TypeError):
        return None


def masked(stdout: str) -> str:
    """Confidence numbers come from a live, non-deterministic model call; mask them for the route-level check."""
    return re.sub(r"\d\.\d\d", "x.xx", stdout)


def main() -> int:
    samples = json.loads((ROOT / "tests/mods/jev-samples.json").read_text(encoding="utf-8"))
    same = 0
    route_same = 0
    for i, prompt in enumerate(samples, 1):
        payload = json.dumps({"prompt": prompt, "session_id": "parity-check"})
        shell_out = run(SHELL_ARGV, payload)
        mod_out = run(MOD_ARGV, payload) if not prompt.lstrip().startswith("/") else ""
        ok = shell_out == mod_out and mod_context(shell_out) == mod_context(mod_out)
        same += ok
        route_same += masked(shell_out) == masked(mod_out)
        ctx = mod_context(shell_out)
        print(f"{i:2d} {'SAME' if ok else 'DIFF'} ctx={'none' if ctx is None else ctx.splitlines()[0][:70]!r}")
        if not ok:
            print(f"   shell: {shell_out!r}\n   mod:   {mod_out!r}")
    print(f"{route_same}/{len(samples)} identical (confidence digits masked)")
    print(f"{same}/{len(samples)} identical")
    return 0 if route_same == len(samples) else 1


if __name__ == "__main__":
    sys.exit(main())
