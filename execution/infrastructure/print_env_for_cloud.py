"""Print the local .env as a clean paste-block for the claude.ai/code cloud environment.

The "Environment variables" box in a claude.ai/code cloud environment accepts
standard .env format (KEY=value, one per line). This script reads the local .env,
drops comments/blanks, dedupes repeated keys (last occurrence wins, matching
python-dotenv behavior), and prints the result so the operator can copy-paste it
in one shot.

Usage (run locally, output goes only to your own terminal — never share it):
    py execution/infrastructure/print_env_for_cloud.py              # names only (safe preview)
    py execution/infrastructure/print_env_for_cloud.py --values     # full KEY=value paste block

Directive: directives/infrastructure/claude_code_web.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def load_env(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    # utf-8-sig: a BOM (e.g. from a Notepad edit) would otherwise silently drop the first key.
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = KEY_RE.match(line)
        if not m:
            continue
        entries[m.group(1)] = m.group(2)  # last occurrence wins
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--values",
        action="store_true",
        help="print full KEY=value lines (default prints key names only)",
    )
    args = parser.parse_args()

    if not ENV_PATH.exists():
        print(f"ERROR: {ENV_PATH} not found", file=sys.stderr)
        return 1

    entries = load_env(ENV_PATH)
    if not entries:
        print("ERROR: no KEY=value entries found in .env", file=sys.stderr)
        return 1

    if args.values:
        print(
            "# Paste everything below into claude.ai/code -> cloud icon -> your "
            "environment -> Environment variables",
            file=sys.stderr,
        )
        for key, value in entries.items():
            print(f"{key}={value}")
    else:
        print(f"# {len(entries)} keys in .env (names only; add --values for the paste block)")
        for key in entries:
            print(key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
