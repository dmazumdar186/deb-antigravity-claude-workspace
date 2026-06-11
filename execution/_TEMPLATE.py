"""<one-line: what this script does, who calls it>.

Usage:
    py execution/<category>/<name>.py --mode balanced [--dry-run] [other args]

Inputs:
    - <input_1>: <type> — <description>
    - <input_2>: <type> — <description>

Outputs:
    - <output_1>: <type> — <description>

Env vars used:
    - <ENV_VAR_1> — <purpose>

Modes:
    cheap     — Haiku 4.5, minimal sampling, fast.
    balanced  — Sonnet 4.6, standard depth (default).
    premium   — Opus 4.7, deep audit, slowest.

See also: directives/<category>/<name>.md
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Workspace-standard model routing per --mode (Karpathy nanochat pattern: one
# int controls complexity. Here it's an enum, but same principle).
MODE_TO_MODEL = {
    "cheap": "claude-haiku-4-5",
    "balanced": "claude-sonnet-4-6",
    "premium": "claude-opus-4-7",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=list(MODE_TO_MODEL.keys()),
        default="balanced",
        help="Tier: cheap (Haiku) / balanced (Sonnet, default) / premium (Opus).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do everything except external API calls / writes. Returns would_* counts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model = MODE_TO_MODEL[args.mode]
    # ... your logic ...
    print(f"mode={args.mode} model={model} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
