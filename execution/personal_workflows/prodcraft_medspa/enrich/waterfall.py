"""
waterfall.py
description: Enrichment waterfall CLI. For every business in --metro whose latest audit bucket is
  qualified (total_score >= --min-score), not do_not_contact, and without a deliverable email (unless
  --force), runs the owner/email waterfall (contact page -> GBP reviews -> state registry -> Apollo ->
  Findymail -> Hunter -> generic-inbox fallback), stopping at the first step that yields an email, then
  verifies the chosen email via MillionVerifier. Updates businesses.owner_name/owner_first/owner_email/
  email_status/email_source and logs one `enrich:step:{name}:{hit|miss}` event per step tried, plus one
  `enrich:step:verify` event, so find-rate per source is measurable from `events`.
inputs: --metro (required), --business-id, --min-score (default 45), --mock, --store {local,supabase},
  --store-root, --limit, --force; env per CONTRACTS.md ("enrich" stage): APOLLO_API_KEY,
  FINDYMAIL_API_KEY|HUNTER_API_KEY, MILLION_VERIFIER_API_KEY, GOOGLE_PLACES_API_KEY.
outputs: businesses rows updated in the store; one stat-line JSON on stdout:
  {"script":"waterfall","in":n,"owner_found":n,"email_found":n,"verified_deliverable":n,
   "by_source":{contact_page:n,gbp_reviews:n,state_registry:n,apollo:n,findymail:n,hunter:n,
   generic_inbox:n},"unresolved":n,"cost_usd":x}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from execution.personal_workflows.prodcraft_medspa.common import config, http, notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import Store, get_store  # noqa: E402

from . import apollo, contact_page, findymail, generic_inbox, gbp_reviews, hunter, state_registry, verify  # noqa: E402
from .context import StepContext, StepResult  # noqa: E402
from .names import domain_from_url  # noqa: E402

STEPS: list[tuple[str, object]] = [
    ("contact_page", contact_page.run),
    ("gbp_reviews", gbp_reviews.run),
    ("state_registry", state_registry.run),
    ("apollo", apollo.run),
    ("findymail", findymail.run),
    ("hunter", hunter.run),
    ("generic_inbox", generic_inbox.run),
]

BY_SOURCE_KEYS = [name for name, _ in STEPS]


def domain_from_business(business: dict) -> str | None:
    return domain_from_url(business.get("final_url") or business.get("website_url"))


def eligible_businesses(
    store: Store, *, metro: str, business_id: str | None, min_score: int, force: bool
) -> list[dict]:
    """qualified (total_score >= min_score) + not do_not_contact + (no deliverable email unless force)."""
    candidates = store.find_businesses(metro=metro, do_not_contact=False)
    if business_id:
        candidates = [b for b in candidates if b.get("id") == business_id]

    out = []
    for business in candidates:
        latest = store.latest_audit(business["id"])
        if not latest or (latest.get("total_score") or 0) < min_score:
            continue
        already_deliverable = business.get("email_status") == "deliverable" and business.get("owner_email")
        if already_deliverable and not force:
            continue
        out.append(business)
    return out


def run_waterfall_for_business(
    business: dict, *, ctx_template: dict, store: Store
) -> tuple[dict, str | None, float]:
    """Run every step for one business, in order, stopping at the first email hit. Returns
    (patch, hit_source, total_cost_usd)."""
    ctx = StepContext(
        mock=ctx_template["mock"],
        fixtures_root=ctx_template["fixtures_root"],
        settings=ctx_template["settings"],
        session=ctx_template["session"],
        domain=domain_from_business(business),
    )

    total_cost = 0.0
    chosen: StepResult | None = None
    hit_source: str | None = None

    for step_name, step_fn in STEPS:
        result: StepResult = step_fn(business, ctx)
        total_cost += result.cost_usd
        store.log_event(
            "business",
            business["id"],
            f"enrich:step:{step_name}:{'hit' if result.hit else 'miss'}",
            {"evidence": result.evidence, "source": result.source},
        )
        if result.hit and result.email and chosen is None:
            chosen = result
            hit_source = step_name
            break

    patch: dict = {
        "owner_name": (chosen.owner_name if chosen else None) or ctx.owner_name,
        "owner_first": (chosen.owner_first if chosen else None) or ctx.owner_first,
    }

    if chosen:
        patch["owner_email"] = chosen.email
        patch["email_source"] = hit_source
        email_status, verify_cost = verify.verify(
            chosen.email,
            mock=ctx.mock,
            fixtures_root=ctx.fixtures_root,
            api_key=ctx.settings.MILLION_VERIFIER_API_KEY,
        )
        total_cost += verify_cost
        patch["email_status"] = email_status
        store.log_event(
            "business", business["id"], "enrich:step:verify", {"email": chosen.email, "email_status": email_status}
        )
    else:
        patch["owner_email"] = None
        patch["email_status"] = None
        patch["email_source"] = None

    return patch, hit_source, total_cost


def run(
    *,
    metro: str,
    business_id: str | None,
    min_score: int,
    mock: bool,
    store: Store,
    limit: int | None,
    force: bool,
    fixtures_root: Path,
    settings,
) -> dict:
    """Programmatic entry point (used by the CLI and by tests) — returns the stat dict."""
    ctx_template = {
        "mock": mock,
        "fixtures_root": fixtures_root,
        "settings": settings,
        "session": http.session(),
    }

    candidates = eligible_businesses(store, metro=metro, business_id=business_id, min_score=min_score, force=force)
    if limit is not None:
        candidates = candidates[:limit]

    stats = {
        "script": "waterfall",
        "in": len(candidates),
        "owner_found": 0,
        "email_found": 0,
        "verified_deliverable": 0,
        "by_source": {k: 0 for k in BY_SOURCE_KEYS},
        "unresolved": 0,
        "cost_usd": 0.0,
    }

    for business in candidates:
        patch, hit_source, cost = run_waterfall_for_business(business, ctx_template=ctx_template, store=store)
        stats["cost_usd"] += cost

        if patch.get("owner_name"):
            stats["owner_found"] += 1
        if patch.get("owner_email"):
            stats["email_found"] += 1
            stats["by_source"][hit_source] = stats["by_source"].get(hit_source, 0) + 1
        else:
            stats["unresolved"] += 1
        if patch.get("email_status") == "deliverable":
            stats["verified_deliverable"] += 1

        store.upsert_business({"id": business["id"], "place_id": business.get("place_id"), **patch})

    stats["cost_usd"] = round(stats["cost_usd"], 4)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="ProdCraft med-spa enrichment waterfall")
    parser.add_argument("--metro", required=True)
    parser.add_argument("--business-id", default=None)
    parser.add_argument("--min-score", type=int, default=45)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    settings = config.bootstrap()
    store_kind = "local" if args.mock else (args.store or settings.store_kind)
    store = get_store(kind=store_kind, root=args.store_root) if store_kind == "local" else get_store(kind=store_kind)
    fixtures_root = Path(__file__).resolve().parent / "fixtures"

    try:
        stats = run(
            metro=args.metro,
            business_id=args.business_id,
            min_score=args.min_score,
            mock=args.mock,
            store=store,
            limit=args.limit,
            force=args.force,
            fixtures_root=fixtures_root,
            settings=settings,
        )
        print(json.dumps(stats))
    except Exception as exc:  # noqa: BLE001 — top-level failure must notify, not crash silently
        notify.error("prodcraft_medspa.enrich.waterfall", str(exc))
        raise


if __name__ == "__main__":
    main()
