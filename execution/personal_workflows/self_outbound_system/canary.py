"""
canary.py
description: Front-door synthetic. Sends 1 real email from the warmed inbox to a monitored Gmail address, then IMAP-polls to confirm INBOX placement (not SPAM / CATEGORY_PROMOTIONS). Hard-fails the daily run on placement failure. Dry-run returns a canned PASS without sending or polling.
inputs: --dry-run/--live, --send-test-email (live only), --output <path>. Env (live only): INSTANTLY_INBOX_EMAIL, CANARY_DESTINATION_EMAIL, CANARY_IMAP_HOST, CANARY_IMAP_USER, CANARY_IMAP_APP_PASSWORD.
outputs: .tmp/self_outbound/canary_<date>.json with {status, placement, latency_s, ...}. Exit 0 on PASS, exit 1 on FAIL.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #9, "Front-door synthetic"). Aligned with ~/.claude/rules/front-door-synthetic.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    TMP_DIR,
    ensure_tmp_dir,
    get_logger,
    print_stat,
    today_str,
    write_json,
)

load_dotenv()
log = get_logger("canary")


def run_dry_run() -> dict:
    """Canned PASS. No email, no IMAP. Used by unit tests + run.py smoke."""
    return {
        "status": "PASS",
        "placement": "INBOX",
        "latency_s": 45,
        "checked_labels": ["INBOX"],
        "dry_run": True,
    }


def run_live(send_test_email: bool) -> dict:
    """Live front-door synthetic. STUBBED — the send + IMAP path needs the
    Phase 1 creds provisioned before it can run. Do NOT flip on without the
    env vars listed in the module docstring."""
    raise NotImplementedError(
        "Live canary not implemented in this scaffold pass. "
        "Flip to live only after Phase 1 provisioning: INSTANTLY_INBOX_EMAIL, "
        "CANARY_DESTINATION_EMAIL, CANARY_IMAP_HOST, CANARY_IMAP_USER, "
        "CANARY_IMAP_APP_PASSWORD in env. Send 1 email, sleep 5 min, IMAP-poll "
        "for the message, assert INBOX and NOT SPAM/PROMOTIONS."
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run (default). Returns canned PASS, no email, no IMAP.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. Actually sends + polls. Requires all env vars.")
    p.add_argument("--send-test-email", action="store_true",
                   help="Live only: send the test email. Without this flag, live "
                        "mode still runs IMAP checks assuming email was sent externally.")
    p.add_argument("--output", type=Path, default=None,
                   help="Override output path.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_tmp_dir()

    if args.dry_run:
        result = run_dry_run()
    else:
        result = run_live(args.send_test_email)

    out_path = args.output or (TMP_DIR / f"canary_{today_str()}.json")
    write_json(out_path, result)
    print_stat("canary", {
        "status": result["status"],
        "placement": result.get("placement"),
        "dry_run": args.dry_run,
        "output": str(out_path),
    })
    # Exit 1 on FAIL so run.py can halt the day
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
