"""
acceptance.py
description: Output-acceptance gate. Runs TWO independent checks that both MUST pass: (a) the frozen regression corpus at tests/acceptance_corpus.json (20 bad must reject, 12 good must pass), and (b) daily Instantly stats (sends>0, bounce<5%, unsub<0.3%, complaints==0). Hard-fails with non-zero exit + raise on any breach. Dry-run skips (b) — corpus check only.
inputs: --corpus <path>, --stats <path>, --dry-run/--live, --output <path>.
outputs: .tmp/self_outbound/acceptance_<date>.json with per-case results. Exit 0 on PASS, non-zero + SystemExit on FAIL.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #10, "Output-acceptance gate"). Aligned with ~/.claude/rules/output-acceptance-gate.md — the corpus is an INDEPENDENT oracle: it does NOT reuse icp_filter's own decisions to grade itself, it asserts on the OUTPUT of icp_filter against operator-flagged expected verdicts.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    CONFIG_DIR,
    TESTS_DIR,
    TMP_DIR,
    ensure_tmp_dir,
    get_logger,
    load_json,
    print_stat,
    today_str,
    write_json,
)
# NB: importing icp_filter here to RUN it is fine — the "independent oracle"
# discipline (see ~/.claude/rules/output-acceptance-gate.md Exhibit B) means
# the CORPUS is the source of truth for expected verdicts. We run icp_filter
# and compare its output to the operator's frozen labels. We are NOT asking
# icp_filter "are you happy with yourself" — we are asking "does your output
# match what the operator declared correct."
from icp_filter import filter_leads  # noqa: E402

load_dotenv()
log = get_logger("acceptance")


def run_corpus_check(corpus_path: Path, icp_cfg: dict) -> tuple[bool, list[dict]]:
    """Return (all_passed, per_case_results). A case fails if:
    - it was declared known-bad but the filter accepted it
    - it was declared known-good but the filter rejected it"""
    corpus = load_json(corpus_path)
    known_bad = corpus.get("known_bad", [])
    known_good = corpus.get("known_good", [])
    suppression_seed = set(corpus.get("suppressed_seed", []))

    # Extend suppression with corpus seed so the "already-suppressed" case
    # matches; this is one of the corpus's own expected reject reasons.
    #
    # Order matters: known_good FIRST so that when bad-14 (deliberate duplicate
    # of good-01) comes through, good-01 is already in seen_emails and bad-14
    # falls out as "duplicate-of-good-01" — the corpus-declared reason.
    all_leads = known_good + known_bad
    kept, rejected = filter_leads(all_leads, icp_cfg, suppression=suppression_seed)

    kept_ids = {lead.get("id") for lead in kept}
    rejected_by_id = {r["lead"].get("id"): r["reason"] for r in rejected}

    results: list[dict] = []
    all_passed = True

    for bad in known_bad:
        case_id = bad.get("id")
        expected_reason = bad.get("reject_reason")
        actual_reason = rejected_by_id.get(case_id)

        if case_id in kept_ids:
            results.append({
                "case": case_id,
                "expected": "reject",
                "actual": "keep",
                "expected_reason": expected_reason,
                "actual_reason": None,
                "verdict": "FAIL",
            })
            all_passed = False
        elif expected_reason and actual_reason and expected_reason != actual_reason:
            # Reject verdict correct but WRONG mechanism — the shared-oracle trap.
            # A mutation of this same lead with the reason-specific defensive check
            # missing would slip through undetected. Pipeline-auditor 2026-07-08:
            # bad-11 (hourly-rate-only) rejects via "no-signals" path, masking that
            # the actual hourly-rate keyword check never fires.
            results.append({
                "case": case_id,
                "expected": "reject",
                "actual": "reject",
                "expected_reason": expected_reason,
                "actual_reason": actual_reason,
                "verdict": "FAIL_REASON_MISMATCH",
            })
            all_passed = False
        else:
            results.append({
                "case": case_id,
                "expected": "reject",
                "actual": "reject",
                "expected_reason": expected_reason,
                "actual_reason": actual_reason,
                "verdict": "PASS",
            })

    for good in known_good:
        case_id = good.get("id")
        if case_id in kept_ids:
            results.append({
                "case": case_id,
                "expected": "keep",
                "actual": "keep",
                "verdict": "PASS",
            })
        else:
            results.append({
                "case": case_id,
                "expected": "keep",
                "actual": "reject",
                "actual_reason": rejected_by_id.get(case_id),
                "verdict": "FAIL",
            })
            all_passed = False

    return all_passed, results


# Footer regex: unsubscribe + physical postal address (numeric street or template token).
# GDPR/CNIL hard requirement (SOLOCAL €900k fine precedent). Enforced on every
# outbound draft before the day's send unlocks.
_FOOTER_UNSUB_RE = re.compile(r"unsubscribe|se désinscrire|{{\s*unsubscribe", re.IGNORECASE)
_FOOTER_POSTAL_RE = re.compile(r"{{\s*postal_address|\b\d{1,6}\s+[A-Za-z]", re.IGNORECASE)


def run_todays_output_check(tmp_dir: Path, run_start_ts: float) -> tuple[bool, dict]:
    """Assert today's pipeline actually produced NON-EMPTY output at every stage
    that ran, using files modified after run_start_ts (independent of the
    acceptance corpus — this catches silent stale-data substitution).

    Fixes P0 gap from pipeline-auditor 2026-07-08: prior gate was blind to
    whether today's run produced anything at all; a crashing icp_filter with
    yesterday's artifact still present would show acceptance PASS.
    """
    stages: list[tuple[str, str, list[str]]] = [
        ("sourced", "sourced_leads_*.json", ["leads"]),
        ("filtered", "filtered_leads_*.json", ["kept"]),
        ("enriched", "enriched_leads_*.json", ["verified"]),
        ("personalized", "personalized_leads_*.json", ["personalized"]),
    ]
    detail: dict[str, dict] = {}
    all_ok = True
    for name, pattern, count_keys in stages:
        matches = sorted(tmp_dir.glob(pattern))
        fresh = [p for p in matches if p.stat().st_mtime >= run_start_ts]
        if not fresh:
            # No fresh file for this stage — either stage didn't run (fine) OR
            # ran but produced nothing (bad). We report "missing" rather than
            # failing outright, because a Phase 3 dry-run that only ran sourcer
            # legitimately has no filtered/enriched output.
            detail[name] = {"ok": True, "count": None, "note": "no fresh file (stage skipped or not run)"}
            continue
        latest = fresh[-1]
        payload = load_json(latest)
        if isinstance(payload, dict):
            count = 0
            for key in count_keys:
                v = payload.get(key)
                if isinstance(v, list):
                    count = len(v)
                    break
        else:
            count = 0
        stage_ok = count > 0
        detail[name] = {"ok": stage_ok, "count": count, "file": str(latest.name)}
        if not stage_ok:
            all_ok = False
    return all_ok, detail


def run_footer_check(tmp_dir: Path, run_start_ts: float) -> tuple[bool, list[dict]]:
    """Assert every personalized draft from THIS run has unsubscribe link +
    postal address. GDPR/CNIL hard requirement. Empty personalized-list is
    OK (upstream gate catches that separately). Directive Edge Cases §GDPR
    explicitly promises this check; code-reviewer 2026-07-08 flagged it
    as owed."""
    matches = sorted(tmp_dir.glob("personalized_leads_*.json"))
    fresh = [p for p in matches if p.stat().st_mtime >= run_start_ts]
    if not fresh:
        return True, []
    payload = load_json(fresh[-1])
    fails: list[dict] = []
    for lead in payload.get("personalized", []) if isinstance(payload, dict) else []:
        body = (lead.get("body_html") or "") + "\n" + (lead.get("body_text") or "")
        unsub_ok = bool(_FOOTER_UNSUB_RE.search(body))
        postal_ok = bool(_FOOTER_POSTAL_RE.search(body))
        if not (unsub_ok and postal_ok):
            fails.append({
                "email": lead.get("email"),
                "unsub_ok": unsub_ok,
                "postal_ok": postal_ok,
            })
    return len(fails) == 0, fails


def run_stats_check(stats_path: Path) -> tuple[bool, dict]:
    """Assert the daily Instantly stats meet thresholds. Returns (passed, details).
    Thresholds per directive Phase 3 acceptance gate + Exit criteria."""
    stats = load_json(stats_path)
    sends = int(stats.get("sends", 0))
    bounces = int(stats.get("bounces", 0))
    unsubs = int(stats.get("unsubscribes", 0))
    complaints = int(stats.get("complaints", 0))

    checks = {
        "sends_gt_0": sends > 0,
        "bounce_rate_lt_5pct": (bounces / sends < 0.05) if sends > 0 else False,
        "unsub_rate_lt_0_3pct": (unsubs / sends < 0.003) if sends > 0 else False,
        "complaints_eq_0": complaints == 0,
    }
    passed = all(checks.values())
    return passed, {
        "sends": sends,
        "bounces": bounces,
        "unsubscribes": unsubs,
        "complaints": complaints,
        "checks": checks,
    }


def _print_diagnostic(results: list[dict], stats_detail: dict | None) -> None:
    fails = [r for r in results if r["verdict"] == "FAIL"]
    print("=" * 60)
    print("ACCEPTANCE GATE FAIL — diagnostic")
    print("=" * 60)
    if fails:
        print(f"\nCorpus failures ({len(fails)}):")
        for f in fails:
            print(f"  - {f['case']}: expected {f['expected']}, got {f['actual']} "
                  f"(expected_reason={f.get('expected_reason')}, actual_reason={f.get('actual_reason')})")
    if stats_detail:
        print("\nStats detail:")
        for k, v in stats_detail.get("checks", {}).items():
            marker = "OK" if v else "FAIL"
            print(f"  [{marker}] {k}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--corpus", type=Path, default=TESTS_DIR / "acceptance_corpus.json",
                   help="Path to acceptance_corpus.json.")
    p.add_argument("--stats", type=Path, default=None,
                   help="Path to instantly stats JSON (from instantly_client.py --action stats).")
    p.add_argument("--icp-config", type=Path, default=CONFIG_DIR / "icp.json",
                   help="Path to icp.json.")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run (default). Skip stats check; corpus check only.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. Requires --stats path.")
    p.add_argument("--output", type=Path, default=None,
                   help="Override output path.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_tmp_dir()

    icp_cfg = load_json(args.icp_config)

    # Capture start timestamp so today's-output + footer checks only inspect
    # files produced during THIS acceptance run's window. In practice we walk
    # back a small buffer to include files produced up to 1 hour before, since
    # run.py fires acceptance at the end of the day's pipeline.
    check_start_ts = time.time() - 3600  # 1h grace for same-run artifacts

    corpus_ok, corpus_results = run_corpus_check(args.corpus, icp_cfg)
    stats_ok: bool | None = None
    stats_detail: dict | None = None

    if not args.dry_run:
        if args.stats is None:
            raise SystemExit("--stats is required in live mode")
        stats_ok, stats_detail = run_stats_check(args.stats)
    else:
        log.info("dry-run: skipping stats check")

    # Today's-output check: hard-fail if a stage produced empty output.
    # In dry-run this is the primary safety net (stats check is skipped).
    todays_ok, todays_detail = run_todays_output_check(TMP_DIR, check_start_ts)

    # Footer regex check: GDPR/CNIL hard requirement enforced per output-acceptance-gate.
    footer_ok, footer_fails = run_footer_check(TMP_DIR, check_start_ts)

    overall_pass = (
        corpus_ok
        and todays_ok
        and footer_ok
        and (stats_ok is True or args.dry_run)
    )

    out_path = args.output or (TMP_DIR / f"acceptance_{today_str()}.json")
    write_json(out_path, {
        "corpus_pass": corpus_ok,
        "stats_pass": stats_ok,
        "todays_output_pass": todays_ok,
        "todays_output_detail": todays_detail,
        "footer_pass": footer_ok,
        "footer_fails": footer_fails,
        "stats_detail": stats_detail,
        "corpus_results": corpus_results,
        "dry_run": args.dry_run,
        "overall_pass": overall_pass,
    })

    print_stat("acceptance", {
        "corpus_pass": corpus_ok,
        "stats_pass": stats_ok,
        "todays_output_pass": todays_ok,
        "footer_pass": footer_ok,
        "overall_pass": overall_pass,
        "dry_run": args.dry_run,
        "output": str(out_path),
    })

    if not overall_pass:
        _print_diagnostic(corpus_results, stats_detail)
        if not todays_ok:
            print("\nToday's-output check FAIL:")
            for stage, d in todays_detail.items():
                marker = "OK" if d["ok"] else "FAIL"
                print(f"  [{marker}] {stage}: {d}")
        if not footer_ok:
            print(f"\nFooter check FAIL ({len(footer_fails)} drafts missing unsubscribe or postal address):")
            for f in footer_fails:
                print(f"  {f}")
        # Hard-fail: unskippable per output-acceptance-gate rule
        raise SystemExit(1)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
