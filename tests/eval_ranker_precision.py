"""
description: Empirical eval for the profile-grounded ranker. Reads
    tests/fixtures/eval_gold_set.json, runs every item through rank_jobs(),
    compares predicted tier vs expected tier, and reports:
      - precision@A, recall@A, F1@A
      - precision@(A|B), recall@(A|B) — "would-show-to-operator" composite
      - SKIP-precision (fraction of expected-SKIP that get SKIP)
      - confusion matrix (3x3: A/B/SKIP predicted x expected, C folded into B)
      - Cohen's kappa (chance-adjusted agreement)
      - Per-item table with track + dims + matched skills + verdict

    Exits non-zero if precision@A < 0.80 OR recall@A < 0.70 OR
    SKIP-precision < 0.80 — these are the floor numbers for "the system works."

inputs:
    - tests/fixtures/eval_gold_set.json
    - GEMINI_API_KEY in env (the ranker calls Gemini)
    - CLI: --gold PATH (default fixtures path), --no-fail (don't exit non-zero
           on threshold miss; for exploratory runs)

outputs:
    - human-readable report on stdout
    - JSON report saved to .tmp/job_search_v2/eval_report_<ts>.json
    - exit 0 on PASS, 1 on FAIL (unless --no-fail)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("eval.ranker")

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    ContractType, JobSource, NormalizedJob, RemoteMode, compute_content_hash,
)
from execution.personal_workflows.job_search_v2.ranker.score import (  # noqa: E402
    rank_jobs,
)

DEFAULT_GOLD = WORKSPACE_ROOT / "tests" / "fixtures" / "eval_gold_set.json"
REPORT_DIR = WORKSPACE_ROOT / ".tmp" / "job_search_v2"

# Thresholds — the system "works" iff all three pass.
P_A_FLOOR = 0.80
R_A_FLOOR = 0.70
P_SKIP_FLOOR = 0.80


def _to_normalized_job(item: dict) -> NormalizedJob:
    """Convert a gold-set item to a NormalizedJob the ranker can score."""
    title = item["title"]
    company = item["company"]
    canonical = f"https://eval.test/{hashlib.sha1(title.encode()).hexdigest()[:12]}"
    ct_map = {
        "cdi": ContractType.CDI, "freelance": ContractType.FREELANCE,
        "cdd": ContractType.CDD, "internship": ContractType.INTERNSHIP,
        "unknown": ContractType.UNKNOWN,
    }
    rm_map = {
        "remote": RemoteMode.REMOTE, "hybrid": RemoteMode.HYBRID,
        "onsite": RemoteMode.ONSITE, "unknown": RemoteMode.UNKNOWN,
    }
    ct = ct_map.get(item.get("contract_type", "unknown").lower(), ContractType.UNKNOWN)
    rm = rm_map.get(item.get("remote_mode", "unknown").lower(), RemoteMode.UNKNOWN)
    h = compute_content_hash(title, company, canonical)
    return NormalizedJob(
        source=JobSource.LINKEDIN_GUEST_API,
        source_id=h[:10],
        url=canonical,
        canonical_url=canonical,
        title=title, company=company, location=item["location"],
        description_snippet=item["description"][:600],
        posted_at=datetime(2026, 6, 26, tzinfo=timezone.utc),
        contract_type=ct, remote_mode=rm,
        fetched_at=datetime.now(timezone.utc),
        content_hash=h,
    )


def _cohen_kappa(confusion: dict[tuple[str, str], int],
                 labels: list[str]) -> float:
    """Compute Cohen's kappa from a confusion matrix dict."""
    total = sum(confusion.values())
    if total == 0:
        return 0.0
    # Agreement = diagonal / total
    p_o = sum(confusion.get((lab, lab), 0) for lab in labels) / total
    # Expected agreement under independence
    p_e = 0.0
    for lab in labels:
        row = sum(confusion.get((lab, c), 0) for c in labels) / total
        col = sum(confusion.get((r, lab), 0) for r in labels) / total
        p_e += row * col
    if p_e == 1.0:
        return 1.0 if p_o == 1.0 else 0.0
    return round((p_o - p_e) / (1.0 - p_e), 4)


def _fold_tier(t: str) -> str:
    """3-class fold: A, B (which absorbs C), SKIP. C is a noisy middle bucket;
    folding it into B matches how the operator actually uses the sheet
    (A = apply now, B = review, SKIP = drop)."""
    if t == "A":
        return "A"
    if t == "SKIP":
        return "SKIP"
    return "B"


def run_eval(gold_path: Path, *, no_fail: bool = False) -> int:
    if not gold_path.exists():
        print(f"FAIL: gold set not found at {gold_path}")
        return 2

    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    items = gold["items"]
    if not items:
        print("FAIL: gold set is empty")
        return 2
    print(f"Gold set: {len(items)} items "
          f"(generated {gold.get('generated_at', 'unknown')}, "
          f"method: {gold.get('method', 'unknown')[:60]}...)")

    # Build NormalizedJobs and a parallel expected-tier list.
    jobs = []
    expected: dict[str, str] = {}
    for item in items:
        nj = _to_normalized_job(item)
        jobs.append(nj)
        expected[nj.content_hash] = _fold_tier(item["expected_tier"])

    print(f"Calling ranker on {len(jobs)} jobs (this may take ~30-60s)...")
    ranked, stats = rank_jobs(jobs)
    print(f"Ranker stats: {stats}")

    # Build per-item results.
    rows: list[dict] = []
    confusion: dict[tuple[str, str], int] = {}
    labels = ["A", "B", "SKIP"]
    for nj, item in zip(jobs, items):
        rj = ranked.get(nj.content_hash)
        if rj is None:
            predicted = "SKIP"  # ranker failed entirely — treat as SKIP
            score = 0.0
            reasoning = "(no ranker response)"
        else:
            predicted = _fold_tier(rj.tier.value)
            score = rj.score
            reasoning = rj.reasoning
        exp = expected[nj.content_hash]
        correct = predicted == exp
        confusion[(predicted, exp)] = confusion.get((predicted, exp), 0) + 1
        rows.append({
            "title": item["title"],
            "company": item["company"],
            "location": item["location"],
            "contract_type": item["contract_type"],
            "expected": exp,
            "predicted": predicted,
            "correct": correct,
            "score": score,
            "rationale": item["rationale"],
            "reasoning": reasoning,
        })

    # Metrics.
    def _precision(label: str) -> float:
        pred_label = sum(confusion.get((label, e), 0) for e in labels)
        true_label = confusion.get((label, label), 0)
        return round(true_label / pred_label, 4) if pred_label else 0.0

    def _recall(label: str) -> float:
        true_label_total = sum(confusion.get((p, label), 0) for p in labels)
        true_label = confusion.get((label, label), 0)
        return round(true_label / true_label_total, 4) if true_label_total else 0.0

    def _f1(label: str) -> float:
        p, r = _precision(label), _recall(label)
        return round(2 * p * r / (p + r), 4) if (p + r) else 0.0

    # A|B composite — "would I see this in the digest?"
    show_pred = sum(confusion.get((p, e), 0) for p in ("A", "B")
                    for e in ("A", "B"))
    show_pred_total = sum(confusion.get((p, e), 0) for p in ("A", "B")
                          for e in labels)
    show_recall_total = sum(confusion.get((p, e), 0) for p in labels
                            for e in ("A", "B"))
    p_show = round(show_pred / show_pred_total, 4) if show_pred_total else 0.0
    r_show = round(show_pred / show_recall_total, 4) if show_recall_total else 0.0

    kappa = _cohen_kappa(confusion, labels)

    p_a, r_a, f1_a = _precision("A"), _recall("A"), _f1("A")
    p_b, r_b = _precision("B"), _recall("B")
    p_skip, r_skip = _precision("SKIP"), _recall("SKIP")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORT_DIR / f"eval_report_{ts}.json"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gold_set_path": str(gold_path.relative_to(WORKSPACE_ROOT)),
        "n_items": len(items),
        "ranker_stats": stats,
        "metrics": {
            "precision_A": p_a, "recall_A": r_a, "f1_A": f1_a,
            "precision_B": p_b, "recall_B": r_b,
            "precision_SKIP": p_skip, "recall_SKIP": r_skip,
            "precision_show_AB": p_show, "recall_show_AB": r_show,
            "cohen_kappa": kappa,
            "accuracy": round(
                sum(confusion.get((lab, lab), 0) for lab in labels)
                / max(1, sum(confusion.values())),
                4,
            ),
        },
        "thresholds": {
            "precision_A_floor": P_A_FLOOR,
            "recall_A_floor": R_A_FLOOR,
            "precision_SKIP_floor": P_SKIP_FLOOR,
        },
        "confusion": [
            {"predicted": p, "expected": e, "count": c}
            for (p, e), c in sorted(confusion.items())
        ],
        "items": rows,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                           encoding="utf-8")

    print("\n" + "=" * 70)
    print(f"RANKER EVAL — {len(items)} items — kappa={kappa:.3f} "
          f"accuracy={report['metrics']['accuracy']:.3f}")
    print("=" * 70)
    print(f"  precision@A   : {p_a:.3f}    (floor: {P_A_FLOOR})")
    print(f"  recall@A      : {r_a:.3f}    (floor: {R_A_FLOOR})")
    print(f"  F1@A          : {f1_a:.3f}")
    print(f"  precision@B   : {p_b:.3f}    recall@B: {r_b:.3f}")
    print(f"  precision@SKIP: {p_skip:.3f}    recall@SKIP: {r_skip:.3f}    (floor: {P_SKIP_FLOOR})")
    print(f"  precision@(A|B) 'would-show': {p_show:.3f}    recall: {r_show:.3f}")
    print()
    print("Confusion (predicted x expected):")
    print(f"  {'pred\\exp':<10}{'A':>8}{'B':>8}{'SKIP':>8}")
    for p in labels:
        row = "  " + f"{p:<10}"
        for e in labels:
            row += f"{confusion.get((p, e), 0):>8}"
        print(row)
    print()
    print(f"Per-item table (only mismatches shown):")
    print(f"  {'title':<46}{'exp':>5}{'pred':>6}{'score':>7}")
    for r in rows:
        if not r["correct"]:
            t = r["title"][:43] + "..." if len(r["title"]) > 43 else r["title"]
            print(f"  {t:<46}{r['expected']:>5}{r['predicted']:>6}{r['score']:>7.2f}")
            print(f"      expected because: {r['rationale']}")
            print(f"      ranker reasoning: {r['reasoning'][:140]}...")
    print()
    print(f"Report: {report_path.relative_to(WORKSPACE_ROOT)}")
    print("=" * 70)

    failed = (p_a < P_A_FLOOR) or (r_a < R_A_FLOOR) or (p_skip < P_SKIP_FLOOR)
    if failed:
        print(f"VERDICT: FAIL — thresholds not met "
              f"(p@A={p_a:.3f} vs floor {P_A_FLOOR}, "
              f"r@A={r_a:.3f} vs {R_A_FLOOR}, "
              f"p@SKIP={p_skip:.3f} vs {P_SKIP_FLOOR})")
        return 0 if no_fail else 1
    print("VERDICT: PASS — all thresholds met")
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1].strip())
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--no-fail", action="store_true",
                        help="Don't exit non-zero on threshold miss.")
    args = parser.parse_args()
    return run_eval(args.gold, no_fail=args.no_fail)


if __name__ == "__main__":
    sys.exit(main())
