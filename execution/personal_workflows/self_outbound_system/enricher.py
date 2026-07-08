"""
enricher.py
description: Enrich filtered leads with email verification signal. Dry-run marks every lead as verified with a high deliverability score without any API call; live mode (STUB) would delegate to execution/enrichment/anymailfinder_lookup.py for missing emails, then execution/enrichment/million_verifier.py for verification.
inputs: --input <path> (filtered leads json), --dry-run/--live, --output <path>. Env (live only): ANYMAILFINDER_API_KEY, MILLION_VERIFIER_API_KEY.
outputs: .tmp/self_outbound/enriched_leads_<timestamp>.json with {"verified": [...], "unverified": [...], "cost_eur": <float>}.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #3).
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
    load_json,
    print_stat,
    timestamp,
    usd_to_eur,
    write_json,
)

load_dotenv()
log = get_logger("enricher")

# Million Verifier list price ~$0.005 per verification. See directive Phase 3
# and personal API notes. This is the reference figure used in dry-run cost
# estimates so operators see order-of-magnitude EUR at plan time.
_MILLION_VERIFIER_USD_PER_HIT = 0.005


def enrich_dry_run(leads: list[dict]) -> tuple[list[dict], list[dict], float]:
    """Mark every lead verified with a canned high score. No API calls, no
    cost. Returns (verified, unverified, cost_eur)."""
    verified: list[dict] = []
    for lead in leads:
        enriched = dict(lead)
        enriched["verified"] = True
        enriched["catchall"] = False
        enriched["deliverable_score"] = 95
        enriched["verifier"] = "dry_run"
        verified.append(enriched)
    return verified, [], 0.0


def enrich_live(leads: list[dict]) -> tuple[list[dict], list[dict], float]:
    """Live enrichment. STUBBED. Delegates to
    execution/enrichment/anymailfinder_lookup.py + million_verifier.py.
    Cost is tracked in EUR and returned as part of the result."""
    raise NotImplementedError(
        "Live enrichment not implemented in this scaffold pass. "
        "Wire up execution/enrichment/anymailfinder_lookup.py and "
        "execution/enrichment/million_verifier.py in a follow-up commit. "
        "Run with --dry-run for now."
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--input", type=Path, required=True,
                   help="Path to filtered leads JSON (from icp_filter.py).")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run mode (default). No API calls, no cost.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. Requires API keys in env.")
    p.add_argument("--output", type=Path, default=None,
                   help="Override output path.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_tmp_dir()

    payload = load_json(args.input)
    kept = payload.get("kept", []) if isinstance(payload, dict) else payload

    if args.dry_run:
        verified, unverified, cost_eur = enrich_dry_run(kept)
    else:
        verified, unverified, cost_eur = enrich_live(kept)

    out_path = args.output or (TMP_DIR / f"enriched_leads_{timestamp()}.json")
    write_json(
        out_path,
        {
            "verified": verified,
            "unverified": unverified,
            "cost_eur": round(cost_eur, 4),
            "dry_run": args.dry_run,
        },
    )
    print_stat(
        "enricher",
        {
            "input": len(kept),
            "verified": len(verified),
            "unverified": len(unverified),
            "cost_eur": round(cost_eur, 4),
            "dry_run": args.dry_run,
            "output": str(out_path),
        },
    )
    # Log the reference unit-cost so the operator can spot-check estimates
    log.info(
        "reference unit costs: million_verifier=%s USD/hit (~%s EUR/hit)",
        _MILLION_VERIFIER_USD_PER_HIT,
        usd_to_eur(_MILLION_VERIFIER_USD_PER_HIT),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
