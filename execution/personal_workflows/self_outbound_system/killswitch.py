"""
killswitch.py
description: One-shot kill switch. --engage sets KILL_SWITCH=1 in the workspace .env and calls instantly_client.py --action pause. --release sets KILL_SWITCH=0 but does NOT auto-resume Instantly (operator must resume in UI + verify canary green). Dry-run prints intent without touching .env or Instantly.
inputs: --engage OR --release (mutually exclusive), --dry-run/--live, --env-file <path>.
outputs: mutates the workspace .env (live). Prints action + rationale to stdout.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #11).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    WORKSPACE_ROOT,
    get_logger,
    print_stat,
)

load_dotenv()
log = get_logger("killswitch")


def _set_env_var(env_path: Path, key: str, value: str) -> bool:
    """Update KEY=VALUE in a .env file. If the key is missing, append it.
    Returns True on success, False if the file doesn't exist. Preserves
    other lines verbatim."""
    if not env_path.exists():
        log.warning("no .env file at %s; refusing to create one", env_path)
        return False
    original = env_path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^{re.escape(key)}=.*$", flags=re.MULTILINE)
    if pattern.search(original):
        new = pattern.sub(f"{key}={value}", original)
    else:
        sep = "" if original.endswith("\n") or not original else "\n"
        new = f"{original}{sep}{key}={value}\n"
    env_path.write_text(new, encoding="utf-8")
    return True


def _pause_instantly_live() -> None:
    """Shell out to instantly_client.py --action pause --live. utf-8 encoding
    per ~/.claude/rules/python-hardening.md rule 1."""
    script = Path(__file__).resolve().parent / "instantly_client.py"
    subprocess.run(
        [sys.executable, str(script), "--action", "pause", "--live"],
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    op = p.add_mutually_exclusive_group(required=True)
    op.add_argument("--engage", action="store_true",
                    help="Set KILL_SWITCH=1 and pause the Instantly campaign.")
    op.add_argument("--release", action="store_true",
                    help="Set KILL_SWITCH=0. Does NOT auto-resume Instantly.")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run (default). Prints intent without touching .env.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. Mutates .env and (for --engage) calls Instantly.")
    p.add_argument("--env-file", type=Path, default=WORKSPACE_ROOT / ".env",
                   help="Path to the .env to mutate. Default: workspace-root .env.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.engage:
        if args.dry_run:
            print("would_engage: set KILL_SWITCH=1 and pause Instantly campaign")
            print_stat("killswitch", {"action": "engage", "dry_run": True})
            return 0
        # Check _set_env_var return code before printing "ENGAGED" — otherwise
        # a missing .env silently masks the failure and the next run.py
        # reads KILL_SWITCH=0 and resumes cold sends. Fixed 2026-07-08 per
        # code-reviewer P0.
        if not _set_env_var(args.env_file, "KILL_SWITCH", "1"):
            msg = (
                f"CRITICAL: killswitch --engage failed to write .env at "
                f"{args.env_file}. Campaign is NOT paused. Refusing to print "
                f"a false-safe 'ENGAGED' confirmation. Fix the .env path and retry."
            )
            log.error(msg)
            print(msg, file=sys.stderr)
            print_stat("killswitch", {"action": "engage", "dry_run": False, "status": "FAIL", "reason": "env_write_failed"})
            raise SystemExit(1)
        _pause_instantly_live()
        print("ENGAGED: KILL_SWITCH=1 set, Instantly campaign paused")
        print_stat("killswitch", {"action": "engage", "dry_run": False, "status": "OK"})
        return 0

    if args.release:
        if args.dry_run:
            print("would_release: set KILL_SWITCH=0. Instantly stays paused; "
                  "operator must resume via UI + verify canary green.")
            print_stat("killswitch", {"action": "release", "dry_run": True})
            return 0
        if not _set_env_var(args.env_file, "KILL_SWITCH", "0"):
            msg = (
                f"CRITICAL: killswitch --release failed to write .env at "
                f"{args.env_file}. KILL_SWITCH is still whatever it was. Fix path and retry."
            )
            log.error(msg)
            print(msg, file=sys.stderr)
            print_stat("killswitch", {"action": "release", "dry_run": False, "status": "FAIL", "reason": "env_write_failed"})
            raise SystemExit(1)
        print("RELEASED: KILL_SWITCH=0 set. Instantly remains paused — "
              "resume via UI and verify canary before next run.")
        print_stat("killswitch", {"action": "release", "dry_run": False, "status": "OK"})
        return 0

    return 1  # argparse should prevent reaching here


if __name__ == "__main__":
    raise SystemExit(main())
