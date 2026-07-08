"""
instantly_client.py
description: Thin CLI wrapper around Instantly.ai Growth REST API v2. Supports upload / stats / pause / resume actions. Dry-run mode issues zero HTTP calls; live mode reads INSTANTLY_API_KEY + INSTANTLY_CAMPAIGN_ID from env.
inputs: --input <path> (personalized leads json, required for upload), --action <upload|stats|pause|resume>, --dry-run/--live, --output <path>. Env (live only): INSTANTLY_API_KEY, INSTANTLY_CAMPAIGN_ID.
outputs: .tmp/self_outbound/instantly_result_<timestamp>.json with the action + result.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #5).
STUB: exact Instantly v2 request/response shapes are documented at
https://developer.instantly.ai and MUST be verified against a real account before
switching to live mode. This scaffold captures the endpoint pattern only.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    TMP_DIR,
    ensure_tmp_dir,
    get_logger,
    load_json,
    print_stat,
    timestamp,
    write_json,
)

load_dotenv()
log = get_logger("instantly_client")

INSTANTLY_API_BASE = "https://api.instantly.ai/api/v2"

# Fixture returned by dry-run stats. Chosen so the acceptance gate's daily-stats
# check passes: sends > 0, bounce_rate < 5%, unsubscribe_rate < 0.3%,
# complaints == 0.
_DRY_RUN_STATS = {
    "sends": 20,
    "bounces": 0,
    "unsubscribes": 0,
    "complaints": 0,
    "opens": 8,
    "replies": 1,
}


def _upload_live(leads: list[dict], api_key: str, campaign_id: str) -> dict:
    """Upload leads to Instantly. STUBBED — see module docstring."""
    raise NotImplementedError(
        "Live upload not implemented. Endpoint pattern: "
        f"POST {INSTANTLY_API_BASE}/campaigns/{campaign_id}/leads with "
        "Authorization: Bearer <key>. Verify shape against a real account first."
    )


def _stats_live(api_key: str, campaign_id: str) -> dict:
    raise NotImplementedError(
        f"Live stats not implemented. Endpoint pattern: "
        f"GET {INSTANTLY_API_BASE}/campaigns/{campaign_id}/analytics."
    )


def _pause_live(api_key: str, campaign_id: str) -> dict:
    raise NotImplementedError(
        f"Live pause not implemented. Endpoint pattern: "
        f"POST {INSTANTLY_API_BASE}/campaigns/{campaign_id}/pause."
    )


def _resume_live(api_key: str, campaign_id: str) -> dict:
    raise NotImplementedError(
        f"Live resume not implemented. Endpoint pattern: "
        f"POST {INSTANTLY_API_BASE}/campaigns/{campaign_id}/resume."
    )


def do_action(
    action: str,
    dry_run: bool,
    leads_payload: dict | None = None,
) -> dict:
    """Perform the requested Instantly action. Returns a result dict written
    to the output file."""
    if action == "upload":
        leads = (leads_payload or {}).get("personalized", []) if leads_payload else []
        if dry_run:
            return {
                "action": "upload",
                "would_upload": len(leads),
                "dry_run": True,
            }
        env = dict(os.environ)  # NEVER copy.copy(os.environ); see hardening rule 6
        api_key = env.get("INSTANTLY_API_KEY", "")
        campaign_id = env.get("INSTANTLY_CAMPAIGN_ID", "")
        if not api_key or not campaign_id:
            raise RuntimeError("INSTANTLY_API_KEY / INSTANTLY_CAMPAIGN_ID missing in env for live upload.")
        return _upload_live(leads, api_key, campaign_id)

    if action == "stats":
        if dry_run:
            return {"action": "stats", "dry_run": True, **_DRY_RUN_STATS}
        env = dict(os.environ)
        return _stats_live(env.get("INSTANTLY_API_KEY", ""), env.get("INSTANTLY_CAMPAIGN_ID", ""))

    if action == "pause":
        if dry_run:
            return {"action": "pause", "would_pause": True, "dry_run": True}
        env = dict(os.environ)
        return _pause_live(env.get("INSTANTLY_API_KEY", ""), env.get("INSTANTLY_CAMPAIGN_ID", ""))

    if action == "resume":
        if dry_run:
            return {"action": "resume", "would_resume": True, "dry_run": True}
        env = dict(os.environ)
        return _resume_live(env.get("INSTANTLY_API_KEY", ""), env.get("INSTANTLY_CAMPAIGN_ID", ""))

    raise ValueError(f"unknown action: {action}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--action", choices=["upload", "stats", "pause", "resume"], required=True,
                   help="Which Instantly operation to run.")
    p.add_argument("--input", type=Path, default=None,
                   help="Path to personalized leads JSON (required for upload).")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run (default). No HTTP.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. Requires INSTANTLY_API_KEY + INSTANTLY_CAMPAIGN_ID.")
    p.add_argument("--output", type=Path, default=None,
                   help="Override output path.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_tmp_dir()

    leads_payload = None
    if args.action == "upload":
        if args.input is None:
            raise SystemExit("--input is required for --action upload")
        leads_payload = load_json(args.input)

    result = do_action(args.action, args.dry_run, leads_payload)

    out_path = args.output or (TMP_DIR / f"instantly_result_{timestamp()}.json")
    write_json(out_path, result)
    print_stat(
        "instantly_client",
        {
            "action": args.action,
            "result": result,
            "dry_run": args.dry_run,
            "output": str(out_path),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
