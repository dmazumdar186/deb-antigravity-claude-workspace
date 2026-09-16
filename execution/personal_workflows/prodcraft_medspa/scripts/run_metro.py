"""
run_metro.py
description: Orchestrator that chains discovery -> audit -> enrich -> preview for one metro, each
    stage run as a subprocess CLI per CONTRACTS.md. Prints a funnel table (found -> operational ->
    audited -> qualified -> owner found -> email verified -> preview built) computed two ways —
    from each stage's self-reported JSON stat line AND cross-checked directly against the store —
    plus per-stage drop reasons and total estimated cost. `--import-csv PATH` inserts an `import`
    stage (discovery.import_csv) at the very front, before `discovery`, for when a manually curated
    CSV of prospects (e.g. from a web-search session with no GOOGLE_PLACES_API_KEY) should seed the
    businesses table instead of / in addition to a live Places search.
inputs: CLI: --metro X [--mock] [--store {local,supabase}] [--store-root P]
    [--stages discovery,audit,enrich,preview] [--import-csv PATH] [--import-source NAME]
    [--sample-n 0] [--sample-only] [--auto-approve] [--skip-vision]
    [--skip-screenshots]
    [--continue-on-error]. Env: whatever the invoked stage subprocesses need (unset is fine with --mock).
outputs: stdout funnel table + JSON summary; .tmp/prodcraft_medspa/runs/{metro}_{timestamp}.json run
    record; on any stage failure, common.notify.error("run_metro", ...) and a non-zero exit unless
    --continue-on-error.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from execution.personal_workflows.prodcraft_medspa.common import notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.config_validate import assert_valid_config  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import get_store  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import (  # noqa: E402
    common_store_args,
    reject_mock_with_supabase,
    run_module,
)

ALL_STAGES = ["discovery", "audit", "enrich", "preview"]
# Optional stage appended by --auto-approve (implied by --mock): preview.approve --metro X --all-review.
# Never in the default list: in production a human approves each preview in the dashboard first.
APPROVE_STAGE = "approve"
# Optional stage inserted (always at the front, before `discovery`) by --import-csv PATH:
# discovery.import_csv --csv PATH --metro X. Never in the default list — it only runs when the
# operator explicitly hands it a CSV (e.g. a metro with no GOOGLE_PLACES_API_KEY).
IMPORT_STAGE = "import"

# stage -> module path under execution.personal_workflows.prodcraft_medspa
STAGE_MODULE = {
    "discovery": "discovery.places_search",
    "audit_full": "audit.audit_site",
    "audit_sample": "audit.sample_audit",
    "enrich": "enrich.waterfall",
    "preview": "preview.build_preview",
    "approve": "preview.approve",
    "import": "discovery.import_csv",
}


def _audit_flags(args: argparse.Namespace) -> list[str]:
    extra: list[str] = []
    if getattr(args, "skip_vision", False):
        extra.append("--skip-vision")
    if getattr(args, "skip_screenshots", False):
        extra.append("--skip-screenshots")
    return extra


def build_stage_args(stage: str, args: argparse.Namespace) -> tuple[str, list[str]]:
    """Return (module_dotted, cli_args) for one stage.

    `audit` always maps to the full `audit.audit_site` run. `--sample-n N` never replaces it: the
    sample is expanded by `expand_stages` into a separate `audit_sample` stage that runs
    `audit.sample_audit --reuse-audits` AFTER the full audit, so it only writes the `metro_stats`
    row (Wilson interval) from audits that already exist. `--sample-only` is the cheap Phase 0
    path (directive step 7): sample N sites, no full audit.
    """
    base = ["--metro", args.metro] + common_store_args(args)

    if stage == "discovery":
        return STAGE_MODULE["discovery"], base

    if stage == "audit":
        return STAGE_MODULE["audit_full"], base + _audit_flags(args)

    if stage == "audit_sample":
        sample_n = int(getattr(args, "sample_n", 0) or 0)
        if sample_n <= 0:
            raise ValueError("audit_sample stage requires --sample-n > 0")
        cli = base + ["--n", str(sample_n)] + _audit_flags(args)
        if not getattr(args, "sample_only", False):
            cli.append("--reuse-audits")
        return STAGE_MODULE["audit_sample"], cli

    if stage == "enrich":
        return STAGE_MODULE["enrich"], base + ["--min-score", str(getattr(args, "min_score", 45) or 45)]

    if stage == "preview":
        return STAGE_MODULE["preview"], base

    if stage == APPROVE_STAGE:
        return STAGE_MODULE["approve"], base + ["--all-review", "--actor", "run_metro"]

    if stage == IMPORT_STAGE:
        csv_path = getattr(args, "import_csv", None)
        if not csv_path:
            raise ValueError("import stage requires --import-csv PATH")
        cli = ["--csv", csv_path, "--metro", args.metro] + common_store_args(args)
        source = getattr(args, "import_source", None)
        if source:
            cli += ["--source", source]
        return STAGE_MODULE["import"], cli

    raise ValueError(f"unknown stage: {stage}")


def expand_stages(stage_list: list[str], args: argparse.Namespace, store_kind: str) -> list[str]:
    """Insert the `audit_sample` stage when --sample-n is set, and `approve` after `preview` when
    --auto-approve is set or --mock is on AND `store_kind == "local"` (the mock chain must reach a
    non-empty daily queue, but `--auto-approve`/`--mock` may never add a live bulk-approve stage
    against a Supabase store — code-reviewer C4/M1; that combination is instead a `parser.error`
    in `main()` before this is called, so this function stays pure: no errors, no I/O, just list
    math the caller's guard has already made safe).

    Default: `audit` (full) then `audit_sample` (metro_stats only, reusing the stored audits).
    `--sample-only`: `audit_sample` replaces `audit` (nothing else is audited).
    Without --sample-n the list is returned unchanged.

    `--import-csv PATH` additionally inserts `import` at index 0 (before everything, including
    `discovery`) whenever it isn't already present — this is pure list math like the rest of the
    function; `build_stage_args("import", ...)` is what actually needs the path and raises if it's
    missing.
    """
    sample_n = int(getattr(args, "sample_n", 0) or 0)
    expanded: list[str] = []
    for stage in stage_list:
        if stage == "audit" and sample_n > 0:
            if not getattr(args, "sample_only", False):
                expanded.append("audit")
            expanded.append("audit_sample")
        else:
            expanded.append(stage)
    if getattr(args, "import_csv", None) and IMPORT_STAGE not in expanded:
        expanded.insert(0, IMPORT_STAGE)
    auto_approve = (getattr(args, "auto_approve", False) or getattr(args, "mock", False)) and store_kind == "local"
    if auto_approve and "preview" in expanded and APPROVE_STAGE not in expanded:
        expanded.insert(expanded.index("preview") + 1, APPROVE_STAGE)
    return expanded


def run_stages(
    stage_list: list[str], args: argparse.Namespace, store_kind: str | None = None
) -> list[dict[str, Any]]:
    """Run each stage in order. Stops at the first failure unless --continue-on-error.

    `store_kind` defaults to `resolve_store_kind(args)` when omitted (existing direct callers of
    `run_stages` need not resolve it themselves), but `main()` always passes the value it already
    computed via `reject_mock_with_supabase()` so the guard's decision is the one that flows into
    `expand_stages()`.
    """
    if store_kind is None:
        from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import resolve_store_kind

        store_kind = resolve_store_kind(args)
    results: list[dict[str, Any]] = []
    stage_list = expand_stages(stage_list, args, store_kind)
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
    """Every preview row, via the Store Protocol's generic list_rows()."""
    return store.list_rows("previews")


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
    operational_ids = {b["id"] for b in operational}
    operational_drop_reasons = Counter(
        (b.get("drop_reason") or ("chain" if b.get("is_chain") else "unknown"))
        for b in found
        if b["id"] not in operational_ids
    )

    audits_by_business: dict[str, dict] = {}
    for b in operational:
        latest = store.latest_audit(b["id"])
        if latest:
            audits_by_business[b["id"]] = latest
    audited = [b for b in operational if b["id"] in audits_by_business]

    qualified = [b for b in audited if audits_by_business[b["id"]].get("bucket") == "qualified"]
    qualified_ids = {b["id"] for b in qualified}
    qualified_drop_reasons = Counter(
        audits_by_business[b["id"]].get("bucket") or "unknown"
        for b in audited
        if b["id"] not in qualified_ids
    )

    owner_found = [b for b in qualified if b.get("owner_name") or b.get("owner_email")]

    email_verified = [b for b in owner_found if b.get("email_status") == "deliverable"]
    email_verified_ids = {b["id"] for b in email_verified}
    # "no_email" (email_status never set — no owner email was even attempted/found) is distinct
    # from a genuine but non-deliverable "unknown" verifier status (pipeline-auditor).
    email_status_reasons = Counter(
        (b.get("email_status") or "no_email") for b in owner_found if b["id"] not in email_verified_ids
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


def build_validation_cfg(store: Any) -> dict[str, Any]:
    """Assemble the subset of `config` keys common/config_validate.py knows how to check. Missing
    keys resolve to None (get_config's own default), which validate_config() treats as "not
    configured" and never flags — this is a startup sanity check on values that ARE set, not a
    completeness check."""
    return {
        "queue_pick": store.get_config("queue_pick"),
        "email_policy": store.get_config("email_policy"),
        "preview_publish_mode": store.get_config("preview_publish_mode"),
        "min_score": store.get_config("min_score"),
        "live_send_confirmed": store.get_config("live_send_confirmed"),
        "preview_host_suffix": store.get_config("preview_host_suffix"),
        "auto_approve_previews": store.get_config("auto_approve_previews"),
        "phase0": store.get_config("phase0"),
    }


def run_record_filename(metro: str) -> str:
    """{metro}_{UTC timestamp to the second}_{short uuid4}.json — the uuid4 suffix guarantees
    uniqueness even when two runs for the same metro start in the same second (pipeline-auditor:
    plain second-resolution timestamps collided in that case)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{metro}_{ts}_{uuid.uuid4().hex[:8]}.json"


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
    parser.add_argument(
        "--import-csv",
        dest="import_csv",
        default=None,
        help="Path to a CSV of prospects; inserts an 'import' stage (discovery.import_csv) before "
        "everything else, including discovery. Columns per discovery/import_csv.py's contract.",
    )
    parser.add_argument(
        "--import-source",
        dest="import_source",
        default=None,
        help="Recorded as discovery_source csv:<source> on imported rows (import_csv.py's own "
        "default is 'manual' when this is omitted).",
    )
    parser.add_argument(
        "--sample-n",
        dest="sample_n",
        type=int,
        default=0,
        help="Also run audit.sample_audit --reuse-audits on N businesses after the full audit "
        "(writes the metro_stats row with a Wilson interval; nothing is audited twice).",
    )
    parser.add_argument(
        "--sample-only",
        dest="sample_only",
        action="store_true",
        help="With --sample-n: run ONLY the N-site sample audit instead of the full audit "
        "(the cheap Phase 0 measurement; pair with --stages discovery,audit).",
    )
    parser.add_argument("--skip-vision", action="store_true")
    parser.add_argument("--skip-screenshots", action="store_true")
    parser.add_argument(
        "--auto-approve",
        dest="auto_approve",
        action="store_true",
        help="After the preview stage run preview.approve --all-review for this metro (skips the dashboard "
        "review step; implied by --mock). Local-store only: `parser.error`s against a Supabase/live "
        "store, where previews stay in 'review' until a human approves.",
    )
    parser.add_argument(
        "--min-score",
        dest="min_score",
        type=int,
        default=None,
        help="Enrich threshold (default: config.min_score, else 45 = qualified). Lower it only for a "
        "degraded-mode metro (no PSI/vision keys) or a dry run; build_preview reads the same config key.",
    )
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    store_kind = reject_mock_with_supabase(parser, args)
    if args.auto_approve and store_kind != "local":
        parser.error(
            "--auto-approve is local-store only; approve a Supabase/live store's previews via "
            "the dashboard, or `preview.approve --preview-id`/`--metro --all-review "
            "--yes-i-reviewed-them` for a deliberate manual bulk approve (run_metro never "
            "passes --yes-i-reviewed-them itself)"
        )
    if args.mock and not args.auto_approve:
        print("[run_metro] --mock implies --auto-approve so the mock chain reaches the daily queue", file=sys.stderr)

    stage_list = [s.strip() for s in args.stages.split(",") if s.strip()]
    unknown = [s for s in stage_list if s not in ALL_STAGES]
    if unknown:
        parser.error(f"unknown stage(s) in --stages: {unknown} (valid: {ALL_STAGES})")
    if args.sample_only and not args.sample_n:
        parser.error("--sample-only requires --sample-n N")

    store = get_store(kind=store_kind, root=args.store_root)

    try:
        assert_valid_config(build_validation_cfg(store))
    except ValueError as exc:
        parser.error(str(exc))

    if args.min_score is None:
        args.min_score = int(store.get_config("min_score", 45) or 45)

    results = run_stages(stage_list, args, store_kind)
    any_failed = any(not r["ok"] for r in results)
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
    out_path = runs_dir / run_record_filename(args.metro)
    out_path.write_text(json.dumps(run_record, indent=2, default=str), encoding="utf-8")
    print(f"\nRun record: {out_path}")

    print(json.dumps({"script": "run_metro", "metro": args.metro, "stages_run": len(results), "any_failed": any_failed}))

    if any_failed and not args.continue_on_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
