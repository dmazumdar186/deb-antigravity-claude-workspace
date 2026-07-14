"""
enricher.py
description: Enrich leads with real emails (via AnymailFinder) and deliverability verification (via Million Verifier). Dry-run marks every lead verified with a canned score; live mode looks up missing emails then verifies them, dropping catchalls and hard-bounces.
inputs: --input <path> (leads json), --dry-run/--live, --min-confidence <int>, --output <path>. Env (live only): ANYMAILFINDER_API_KEY, MILLION_VERIFIER_API_KEY.
outputs: .tmp/self_outbound/enriched_leads_<timestamp>.json with {"verified": [...], "unverified": [...], "cost_eur": <float>}.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #3).
Live mode delegates to execution/enrichment/anymailfinder_lookup.py (find_email) and execution/enrichment/million_verifier.py (verify_email) as libraries.
Cost model: AnymailFinder ~$0.01/lookup, Million Verifier ~$0.005/verification. 100 leads ~= $1.50 total (EUR 1.38).
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
    usd_to_eur,
    write_json,
)

# Import the workspace's existing enrichment library functions
_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_WORKSPACE_ROOT / "execution" / "enrichment"))

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


_ANYMAILFINDER_USD_PER_HIT = 0.01     # AnymailFinder person-search list price
_ANYMAILFINDER_MIN_CONFIDENCE = 70    # per Phase 1 tolerance; catch-all/generic drop under 70

# Result codes from Million Verifier v3 API — only 'ok' is safe to send.
_MV_ACCEPT_CODES = {"ok"}
_MV_DROP_CODES = {"invalid", "disposable", "role", "unknown"}
_MV_CATCHALL_CODE = "catch_all"  # separate class — reject per catch-all avoidance


def enrich_live(
    leads: list[dict],
    min_confidence: int = _ANYMAILFINDER_MIN_CONFIDENCE,
    accept_catchall: bool = False,
) -> tuple[list[dict], list[dict], float]:
    """Live enrichment. For each lead:
    1. If email is present + valid, skip lookup (still verify).
    2. Otherwise, call AnymailFinder.find_email(domain, company, owner_name).
    3. Verify the found email via Million Verifier.
    4. Keep only leads with a deliverable (result='ok') email >= min_confidence.

    Returns (verified, unverified, cost_eur). Never raises on per-lead errors —
    logs and moves on so the batch completes.
    """
    anymail_key = os.environ.get("ANYMAILFINDER_API_KEY")
    mv_key = os.environ.get("MILLION_VERIFIER_API_KEY")
    if not anymail_key:
        raise RuntimeError("ANYMAILFINDER_API_KEY not set — required for live enrichment")
    if not mv_key:
        raise RuntimeError("MILLION_VERIFIER_API_KEY not set — required for live enrichment")

    # Lazy import — only pull heavy deps in live mode
    try:
        from anymailfinder_lookup import find_email  # type: ignore
        from million_verifier import verify_email  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            f"Could not import enrichment libs (added by sys.path append): {e}"
        ) from e

    verified: list[dict] = []
    unverified: list[dict] = []
    total_cost_usd = 0.0

    for i, lead in enumerate(leads):
        enriched = dict(lead)
        email = (enriched.get("email") or "").strip().lower()

        # If email is present + valid, skip lookup (but still verify)
        if email and "@" in email:
            enriched["email_source"] = "already_present"
        else:
            domain = enriched.get("domain", "").strip().lower()
            company = enriched.get("company", "").strip()
            owner_name = enriched.get("name", "").strip()

            # If no domain, try to derive from company via LinkedIn/website lookup —
            # but AnymailFinder can accept just company name (uses its own domain lookup).
            if not (domain or company):
                unverified.append({
                    "lead": lead,
                    "reason": "no-domain-no-company",
                })
                continue

            try:
                result = find_email(
                    domain=domain, company_name=company,
                    api_key=anymail_key, owner_name=owner_name,
                )
                total_cost_usd += _ANYMAILFINDER_USD_PER_HIT
            except Exception as e:  # noqa: BLE001
                # Per-lead failure — log + skip, don't blow up the batch
                log.warning(f"anymailfinder lookup failed for lead {i} ({company}): {e}")
                unverified.append({"lead": lead, "reason": f"amf-error:{type(e).__name__}"})
                continue

            if not result:
                unverified.append({"lead": lead, "reason": "amf-no-result"})
                continue

            found_email = (result.get("email") or "").strip().lower()
            confidence = int(result.get("confidence", 0) or 0)
            if not found_email or "@" not in found_email:
                unverified.append({"lead": lead, "reason": "amf-empty-email"})
                continue
            if confidence < min_confidence:
                unverified.append({
                    "lead": lead,
                    "reason": f"amf-low-confidence:{confidence}",
                })
                continue

            enriched["email"] = found_email
            enriched["email_source"] = "anymailfinder"
            enriched["email_confidence"] = confidence
            email = found_email
            if not domain:
                enriched["domain"] = found_email.split("@", 1)[1]

        # Verify with Million Verifier
        try:
            mv_result = verify_email(email, mv_key)
            total_cost_usd += 0.005  # Million Verifier list price ~$0.005/verify
        except Exception as e:  # noqa: BLE001
            log.warning(f"million_verifier failed for lead {i} ({email}): {e}")
            unverified.append({"lead": lead, "reason": f"mv-error:{type(e).__name__}"})
            continue

        result_code = (mv_result.get("result") or "").lower()
        quality = int(mv_result.get("quality_score", 0) or 0)

        enriched["verifier"] = "million_verifier"
        enriched["verifier_result"] = result_code
        enriched["deliverable_score"] = quality
        enriched["catchall"] = (result_code == _MV_CATCHALL_CODE)

        if result_code in _MV_ACCEPT_CODES:
            enriched["verified"] = True
            verified.append(enriched)
        elif result_code == _MV_CATCHALL_CODE:
            if accept_catchall:
                enriched["verified"] = True
                verified.append(enriched)
            else:
                unverified.append({"lead": lead, "reason": "catchall-domain"})
        else:
            unverified.append({
                "lead": lead,
                "reason": f"mv-drop:{result_code or 'unknown'}",
                "quality_score": quality,
            })

    cost_eur = usd_to_eur(total_cost_usd)
    log.info(
        f"live enrich: verified={len(verified)} unverified={len(unverified)} "
        f"cost=EUR {cost_eur:.4f}"
    )
    return verified, unverified, cost_eur


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--input", type=Path, required=True,
                   help="Path to leads JSON (from sourcer.py or icp_filter.py).")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run mode (default). No API calls, no cost.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. Requires API keys in env.")
    p.add_argument("--min-confidence", type=int, default=_ANYMAILFINDER_MIN_CONFIDENCE,
                   help="Min AnymailFinder confidence for keep (default: 70).")
    p.add_argument("--accept-catchall", action="store_true",
                   help="Keep catch-all-domain emails. Default: drop them.")
    p.add_argument("--output", type=Path, default=None,
                   help="Override output path.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_tmp_dir()

    payload = load_json(args.input)
    # Accept input from either icp_filter (kept key) or sourcer (leads key)
    if isinstance(payload, dict):
        leads = payload.get("kept") or payload.get("leads") or payload.get("verified") or []
    else:
        leads = payload

    if args.dry_run:
        verified, unverified, cost_eur = enrich_dry_run(leads)
    else:
        verified, unverified, cost_eur = enrich_live(
            leads,
            min_confidence=args.min_confidence,
            accept_catchall=args.accept_catchall,
        )

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
            "input": len(leads),
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
