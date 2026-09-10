"""
run_metro.py
description: Orchestrator that chains discovery -> audit -> enrich -> preview for one metro, each
    stage run as a subprocess CLI per CONTRACTS.md. Prints a funnel table (found -> operational ->
    audited -> qualified -> owner found -> email verified -> preview built) computed two ways —
    from each stage's self-reported JSON stat line AND cross-checked directly against the store —
    plus per-stage drop reasons and total estimated cost.
inputs: CLI: --metro X [--mock] [--store {local,supabase}] [--store-root P]
    [--stages discovery,audit,enrich,preview] [--sample-n 0] [--skip-vision] [--skip-screenshots]
    [--continue-on-error]. Env: whatever the invoked stage subprocesses need (unset is fine with --mock).
outputs: stdout funnel table + JSON summary; .tmp/prodcraft_medspa/runs/{metro}_{timestamp}.json run
    record; on any stage failure, common.notify.error("run_metro", ...) and a non-zero exit unless
    --continue-on-error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from execution.personal_workflows.prodcraft_medspa.common import notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import (  # noqa: E402
    LocalStore,
    SupabaseStore,
    get_store,
)
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import (  # noqa: E402
    common_store_args,
    run_module,
)

ALL_STAGES = ["discovery", "audit", "enrich", "preview"]

# stage -> module path under execution.personal_workflows.prodcraft_medspa
STAGE_MODULE = {
    "discovery": "discovery.places_search",
    "audit_full": "audit.audit_site",
    "audit_sample": "audit.sample_audit",
    "enrich": "enrich.waterfall",
    "preview": "preview.build_preview",
}


def build_stage_args(stage: str, args: argparse.Namespace) -> tuple[str, list[str]]:
    """Return (module_dotted, cli_args) for one stage."""
    base = ["--metro", args.metro] + common_store_args(args)

    if stage == "discovery":
        return STAGE_MODULE["discovery"], base

    if stage == "audit":
        if args.sample_n and args.sample_n > 0:
            return STAGE_MODULE["audit_sample"], base + ["--n", str(args.sample_n)]
        extra = []
        if args.skip_vision:
            extra.append("--skip-vision")
        if args.skip_screenshots:
            extra.append("--skip-screenshots")
        return STAGE_MODULE["audit_full"], base + extra

    if stage == "enrich":
        return STAGE_MODULE["enrich"], base + ["--min-score", "45"]

    if stage == "preview":
        return STAGE_MODULE["preview"], base

    raise ValueError(f"unknown stage: {stage}")


def run_stages(stage_list: list[str], args: argparse.Namespace) -> list[dict[str, Any]]:
    """Run each stage in order. Stops at the first failure unless --continue-on-error."""
    results: list[dict[str, Any]] = []
    for stage in stage_list:
        module, cli_args = build_stage_args(stage, args)
        print(f"\n=== stage: {stage} ({module}) ===", file=sys.stderr)
        result = run_module(module, cli_args)
        result["stage"] = stage
        results.append(result)

        if result["ok"]:
            print(f"[run_metro] {stage} OK: {json.dumps(result['stat'])}", file=sys.stderr)
        else:
            msg = f"stage '{stage}' ({module}) failed: {result['error']}"
            print(f"[run_metro] {msg}", file=sys.stderr)
            notify.error("run_metro", msg, count=1)
            if not args.continue_on_error:
                break
    return results


# ---------------------------------------------------------------------------
# Store cross-check (funnel computed from the store, not just stat lines)
# ---------------------------------------------------------------------------


def _all_previews(store: Any) -> list[dict]:
    """Best-effort preview-row listing across either Store implementation.

    The Store Protocol (CONTRACTS.md) has no generic "list previews" method; this reaches into
    each concrete implementation's own storage (LocalStore's JSON file, SupabaseStore's REST
    endpoint) rather than widening the shared interface for one orchestrator-only need.
    """
    if isinstance(store, LocalStore):
        return store._read("previews")  # noqa: SLF001 — same package, documented above
    if isinstance(store, SupabaseStore):
        resp = store._request("GET", "previews", headers=store._headers())  # noqa: SLF001
        return resp.json()
    return []


def compute_funnel(store: Any, metro: str) -> dict[str, Any]:
    """Cross-check funnel numbers computed directly from the store for `metro`.

    Each stage below narrows the *previous stage's surviving population* (not the raw `found`
    count), so percentages read as "of the businesses that reached this stage, how many
    advanced" — the shape the spec's funnel table implies (D-something in
    docs/audits/prodcraft_medspa_panel_pass_2026-09-10.md, Saraev #6: "probability multiplication").
    """
    businesses = store.find_businesses(metro=metro)
    found = businesses

    operational = [b for b in found if not b.get("is_chain") and b.get("drop_reason") is None]
    operational_drop_reasons = Counter(
        (b.get("drop_reason") or ("chain" if b.get("is_chain") else "unknown"))
        for b in found
        if b not in operational
    )

    audits_by_business: dict[str, dict] = {}
    for b in operational:
        latest = store.latest_audit(b["id"])
        if latest:
            audits_by_business[b["id"]] = latest
    audited = [b for b in operational if b["id"] in audits_by_business]

    qualified = [b for b in audited if audits_by_business[b["id"]].get("bucket") == "qualified"]
    qualified_drop_reasons = Counter(
        audits_by_business[b["id"]].get("bucket") or "unknown"
        for b in audited
        if b not in qualified
    )

    owner_found = [b for b in qualified if b.get("owner_name") or b.get("owner_email")]

    email_verified = [b for b in owner_found if b.get("email_status") == "deliverable"]
    email_status_reasons = Counter(
        b.get("email_status") or "unknown" for b in owner_found if b not in email_verified
    )

    previews = _all_previews(store)
    business_ids_with_preview = {p.get("business_id") for p in previews if p.get("business_id")}
    preview_built = [b for b in email_verified if b["id"] in business_ids_with_preview]

    stages = [
        ("found", len(found), None),
        ("operational (kept)", len(operational), dict(operational_drop_reasons) or None),
        ("audited", len(audited), {"not_yet_audited": len(operational) - len(audited)} if len(operational) > len(audited) else None),
        ("qualified", len(qualified), dict(qualified_drop_reasons) or None),
        ("owner found", len(owner_found), {"no_owner_found": len(qualified) - len(owner_found)} if len(qualified) > len(owner_found) else None),
        ("email verified", len(email_verified), dict(email_status_reasons) or None),
        ("preview built", len(preview_built), {"no_preview": len(email_verified) - len(preview_built)} if len(email_verified) > len(preview_built) else None),
    ]
    return {"metro": metro, "stages": stages}


def _pct(count: int, prev: int) -> str:
    if prev <= 0:
        return "n/a"
    return f"{100.0 * count / prev:.1f}%"


def print_funnel_table(funnel: dict[str, Any]) -> None:
    print(f"\nFunnel — {funnel['metro']} (store cross-check)")
    print(f"{'stage':<20} {'count':>6} {'% of prev':>10}  drop reasons")
    prev = None
    for name, count, reasons in funnel["stages"]:
        pct = "—" if prev is None else _pct(count, prev)
        reason_str = ", ".join(f"{k}={v}" for k, v in (reasons or {}).items()) or "-"
        print(f"{name:<20} {count:>6} {pct:>10}  {reason_str}")
        prev = count


def estimate_total_cost(stage_results: list[dict[str, Any]]) -> float:
    """Sum any of "cost_usd" / "est_cost_usd" / "llm_cost_usd" present in a stage's stat line
    (different stages name their cost field differently — discovery reports "est_cost_usd",
    audit/preview/outreach report "llm_cost_usd", enrich reports "cost_usd"). Best-effort: stages
    that don't report cost contribute 0, so this is a floor, not a guaranteed total (see
    PROJECT_SPEC.md §12 for the ~$90-130/mo reference figure this should stay in the neighborhood
    of)."""
    total = 0.0
    for r in stage_results:
        stat = r.get("stat") or {}
        for key in ("cost_usd", "est_cost_usd", "llm_cost_usd"):
            cost = stat.get(key)
            if isinstance(cost, (int, float)):
                total += float(cost)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metro", required=True)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", dest="store_root", default=None)
    parser.add_argument("--stages", default=",".join(ALL_STAGES))
    parser.add_argument("--sample-n", dest="sample_n", type=int, default=0)
    parser.add_argument("--skip-vision", action="store_true")
    parser.add_argument("--skip-screenshots", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    stage_list = [s.strip() for s in args.stages.split(",") if s.strip()]
    unknown = [s for s in stage_list if s not in ALL_STAGES]
    if unknown:
        parser.error(f"unknown stage(s) in --stages: {unknown} (valid: {ALL_STAGES})")

    results = run_stages(stage_list, args)
    any_failed = any(not r["ok"] for r in results)

    store = get_store(kind=args.store, root=args.store_root) if args.store_root else get_store(kind=args.store)
    funnel = compute_funnel(store, args.metro)
    print_funnel_table(funnel)

    total_cost = estimate_total_cost(results)
    print(f"\nEstimated total cost this run (self-reported, floor only): ${total_cost:.2f}")

    print("\nStat lines (self-reported, per stage):")
    for r in results:
        print(f"  {r['stage']}: {json.dumps(r.get('stat'))}")

    run_record = {
        "metro": args.metro,
        "started_stages": stage_list,
        "mock": args.mock,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "stage_results": [
            {k: v for k, v in r.items() if k not in ("stdout", "stderr")} for r in results
        ],
        "funnel": funnel,
        "estimated_total_cost_usd": total_cost,
        "any_failed": any_failed,
    }
    runs_dir = REPO_ROOT / ".tmp" / "prodcraft_medspa" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = runs_dir / f"{args.metro}_{ts}.json"
    out_path.write_text(json.dumps(run_record, indent=2, default=str), encoding="utf-8")
    print(f"\nRun record: {out_path}")

    print(json.dumps({"script": "run_metro", "metro": args.metro, "stages_run": len(results), "any_failed": any_failed}))

    if any_failed and not args.continue_on_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
