"""
sourcer.py
description: Source raw B2B leads for the self-outbound system. Dry-run returns the frozen 3-lead fixture; live mode (STUB) would call Apify Google Maps + LinkedIn Actors under a $5/mo CU budget.
inputs: --segment <name>, --limit <int>, --dry-run/--live, --output <path>. Env (live only): APIFY_API_TOKEN.
outputs: .tmp/self_outbound/sourced_leads_<timestamp>.json — list of raw leads with email, name, title, company, domain, linkedin_url, notes, source.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #1).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# _common lives next to this script; import via package-relative path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    FIXTURES_DIR,
    TMP_DIR,
    ensure_tmp_dir,
    get_logger,
    load_json,
    print_stat,
    timestamp,
    write_json,
)

load_dotenv()
log = get_logger("sourcer")


def source_dry_run(segment: str | None, limit: int) -> list[dict]:
    """Return leads from the frozen fixture. Segment filter is best-effort based
    on the fixture's segment_hint field; if segment is None, return all."""
    fixture_path = FIXTURES_DIR / "leads_seed.json"
    payload = load_json(fixture_path)
    leads: list[dict] = payload.get("leads", [])
    if segment:
        leads = [lead for lead in leads if lead.get("segment_hint") == segment]
    leads = leads[:limit] if limit > 0 else leads
    # Tag each lead with the synthetic source so downstream can distinguish
    for lead in leads:
        lead.setdefault("source", "fixture:leads_seed")
    return leads


def source_live(segment: str | None, limit: int) -> list[dict]:
    """Live sourcing via Apify. STUBBED. See directive Phase 3 for the two
    Actors used: `compass/crawler-google-places` + a LinkedIn public-profile
    Actor. Stays under $5/mo CU budget. Not implemented in this scaffold pass."""
    raise NotImplementedError(
        "Live sourcing not implemented in this scaffold pass. "
        "See directive Phase 3.1 for the Apify Actor integration plan. "
        "Run with --dry-run for now."
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--segment", type=str, default=None,
                   help="Optional segment name (see config/icp.json).")
    p.add_argument("--limit", type=int, default=20,
                   help="Max leads to source. 0 = no cap.")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run mode (default). Returns fixture leads.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. Requires APIFY_API_TOKEN in env.")
    p.add_argument("--output", type=Path, default=None,
                   help="Override output path. Default: .tmp/self_outbound/sourced_leads_<ts>.json.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_tmp_dir()
    if args.dry_run:
        leads = source_dry_run(args.segment, args.limit)
    else:
        leads = source_live(args.segment, args.limit)

    out_path = args.output or (TMP_DIR / f"sourced_leads_{timestamp()}.json")
    write_json(out_path, {"leads": leads, "dry_run": args.dry_run})
    print_stat(
        "sourcer",
        {
            "sourced": len(leads),
            "sources": ["apify_gmaps", "apify_linkedin"] if not args.dry_run else ["fixture:leads_seed"],
            "dry_run": args.dry_run,
            "output": str(out_path),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
