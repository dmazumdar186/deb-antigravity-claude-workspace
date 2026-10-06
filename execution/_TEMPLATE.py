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
    cheap     — claude-sonnet-5-5, bulk tier (Haiku is banned).
    balanced  — claude-opus-5-5, standard tier (default).
    premium   — claude-fable-5-1, judgement tier, slowest.

See also: directives/<category>/<name>.md
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Workspace-standard model routing per --mode (Karpathy nanochat pattern: one
# int controls complexity. Here it's an enum, but same principle).
# Haiku 4.5 is BANNED per ~/.claude/rules/model-tier.md, so "cheap" maps to the
# bulk tier (Sonnet 5.5, Jev-routed tiers 2026-10-06). Full names pinned; bare
# aliases drift across providers.
MODE_TO_MODEL = {
    "cheap": "claude-sonnet-5-5",
    "balanced": "claude-opus-5-5",
    "premium": "claude-fable-5-1",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=list(MODE_TO_MODEL.keys()),
        default="balanced",
        help="Tier: cheap / balanced (default) / premium = Sonnet 5.5 / Opus 5.5 / Fable 5.1 (Jev tiers, 2026-10-06). Haiku is banned.",
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
