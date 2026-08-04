#!/usr/bin/env python3
"""
G-Eval harness for AgentUp's scoring endpoint.

Purpose (per workspace `eval-first` rule + Sutskever/AI-safety panel lens):
  1. Score-consistency:  run the SAME transcript through the scoring model
     N times and measure variance per dimension. High variance on a fixed
     input = an unreliable judge.
  2. Golden-set discrimination: verify that a curated "known A+" transcript
     scores above a threshold AND a "known-fail" transcript scores below.

Usage:
    py tests/g_eval_scoring.py [--base https://agentup-iag.pages.dev] [--n 5]

Exits 0 if all checks pass, 1 otherwise. Emits a structured summary at end.

Notes:
- Uses standard library only (urllib) — no external deps.
- N defaults to 3 to stay within Anthropic/Gemini free-tier budgets.
- Golden transcripts are picked to be unambiguous — if the model is
  functioning at all, these must land on opposite ends of the scoring range.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

# --- Golden set ---

GOLDEN_A_PLUS = {
    "label": "A+ transcript — empathy + accurate resolution + clear close",
    "scenario": "Customer noticed a duplicate 49.99 EUR charge on last month's bill.",
    "difficulty": "Beginner",
    "transcript": [
        {"role": "customer", "text": "Hi, I've been charged twice on my last bill. It's for 49.99 EUR."},
        {"role": "agent",    "text": "I'm sorry to see that — I completely understand how frustrating a duplicate charge is. Let me pull up your account right now and take a look."},
        {"role": "customer", "text": "Thank you, I appreciate it."},
        {"role": "agent",    "text": "I can confirm the duplicate on the 12th. I'm reversing it immediately — you should see the 49.99 EUR refunded within 3-5 business days, and I'll send a confirmation to your email now. Anything else I can help with today?"},
        {"role": "customer", "text": "No, that's perfect. Thanks so much."},
        {"role": "agent",    "text": "You're very welcome. Have a great rest of your day."},
    ],
    "min_overall_score": 80,   # if the model returns <80 on this, something is very wrong
    "min_empathy_score": 75,
    "min_resolution_score": 75,
}

GOLDEN_FAIL = {
    "label": "Fail transcript — dismissive, no resolution, unprofessional",
    "scenario": "Customer noticed a duplicate 49.99 EUR charge on last month's bill.",
    "difficulty": "Beginner",
    "transcript": [
        {"role": "customer", "text": "Hi, I've been charged twice on my last bill. It's for 49.99 EUR."},
        {"role": "agent",    "text": "u sure? bills always look weird tbh."},
        {"role": "customer", "text": "Yes I checked my bank statement. Please refund it."},
        {"role": "agent",    "text": "can't do that. not my dept."},
        {"role": "customer", "text": "Can you transfer me to who can?"},
        {"role": "agent",    "text": "nope. try again tomorrow maybe."},
    ],
    "max_overall_score": 45,   # if the model gives this >45, judge is broken
    "max_professionalism_score": 45,
}

# --- HTTP client ---

def post_score(base: str, payload: Dict[str, Any], timeout: int = 45, retries: int = 3) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(
            base.rstrip("/") + "/api/claude",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Origin": base.rstrip("/"),
                "User-Agent": "AgentUp-GEval/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code not in (403, 429, 502, 503, 504):
                raise
            time.sleep(1.5 * (attempt + 1))  # backoff
        except urllib.error.URLError as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    assert last_err is not None
    raise last_err

# --- Test runners ---

def run_consistency(base: str, golden: Dict[str, Any], n: int) -> Dict[str, Any]:
    payload = {
        "mode": "score",
        "scenario": golden["scenario"],
        "difficulty": golden["difficulty"],
        "transcript": golden["transcript"],
    }
    scores: Dict[str, List[int]] = {"overall": [], "empathy": [], "accuracy": [], "resolution": [], "professionalism": []}
    errors: List[str] = []
    for i in range(n):
        try:
            if i > 0: time.sleep(1.0)  # gentle pacing between consistency runs
            r = post_score(base, payload)
            scores["overall"].append(int(r["overallScore"]))
            scores["empathy"].append(int(r["empathyScore"]))
            scores["accuracy"].append(int(r["accuracyScore"]))
            scores["resolution"].append(int(r["resolutionScore"]))
            scores["professionalism"].append(int(r["professionalismScore"]))
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError, ValueError) as e:
            errors.append(f"run {i + 1}: {type(e).__name__}: {e}")
    summary: Dict[str, Any] = {"n": n, "successful_runs": len(scores["overall"]), "errors": errors, "per_dim": {}}
    for dim, vals in scores.items():
        if len(vals) < 2:
            summary["per_dim"][dim] = {"count": len(vals), "mean": vals[0] if vals else None, "stdev": None}
        else:
            summary["per_dim"][dim] = {
                "count": len(vals), "mean": round(statistics.mean(vals), 1),
                "stdev": round(statistics.stdev(vals), 2), "min": min(vals), "max": max(vals),
                "range": max(vals) - min(vals),
            }
    return summary


def run_discrimination(base: str) -> Dict[str, Any]:
    a = post_score(base, {
        "mode": "score",
        "scenario": GOLDEN_A_PLUS["scenario"],
        "difficulty": GOLDEN_A_PLUS["difficulty"],
        "transcript": GOLDEN_A_PLUS["transcript"],
    })
    f = post_score(base, {
        "mode": "score",
        "scenario": GOLDEN_FAIL["scenario"],
        "difficulty": GOLDEN_FAIL["difficulty"],
        "transcript": GOLDEN_FAIL["transcript"],
    })
    checks = []
    checks.append(("A+ overall >= 80",             int(a["overallScore"])         >= GOLDEN_A_PLUS["min_overall_score"],        int(a["overallScore"])))
    checks.append(("A+ empathy >= 75",             int(a["empathyScore"])         >= GOLDEN_A_PLUS["min_empathy_score"],        int(a["empathyScore"])))
    checks.append(("A+ resolution >= 75",          int(a["resolutionScore"])      >= GOLDEN_A_PLUS["min_resolution_score"],     int(a["resolutionScore"])))
    checks.append(("Fail overall <= 45",           int(f["overallScore"])         <= GOLDEN_FAIL["max_overall_score"],          int(f["overallScore"])))
    checks.append(("Fail professionalism <= 45",   int(f["professionalismScore"]) <= GOLDEN_FAIL["max_professionalism_score"],  int(f["professionalismScore"])))
    checks.append(("A+ overall > Fail overall",   int(a["overallScore"])         >  int(f["overallScore"]),                    None))
    return {"a_plus": a, "fail": f, "checks": [{"name": n, "pass": p, "value": v} for (n, p, v) in checks]}

# --- Main ---

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://agentup-iag.pages.dev")
    ap.add_argument("--n", type=int, default=3, help="Consistency runs per golden transcript (default 3)")
    ap.add_argument("--consistency-stdev-cap", type=float, default=10.0,
                    help="Max acceptable per-dimension standard deviation across N runs on the SAME transcript (default 10)")
    args = ap.parse_args()

    print(f"G-Eval harness — target: {args.base}")
    print("=" * 70)
    all_ok = True

    print(f"\n[1/2] Score consistency (N={args.n} runs on A+ transcript)")
    cons = run_consistency(args.base, GOLDEN_A_PLUS, args.n)
    print(f"  successful runs: {cons['successful_runs']} / {cons['n']}")
    if cons["errors"]:
        print(f"  errors: {cons['errors']}")
        all_ok = False
    for dim, stats in cons["per_dim"].items():
        if stats.get("stdev") is None:
            print(f"    {dim:16s} — not enough data")
            continue
        marker = " OK " if stats["stdev"] <= args.consistency_stdev_cap else "HIGH"
        if stats["stdev"] > args.consistency_stdev_cap: all_ok = False
        print(f"    {dim:16s} mean={stats['mean']:5.1f}  stdev={stats['stdev']:5.2f}  range={stats['range']:3d}   [{marker}]")

    print(f"\n[2/2] Discrimination — A+ vs fail transcripts")
    disc = run_discrimination(args.base)
    for c in disc["checks"]:
        mark = "PASS" if c["pass"] else "FAIL"
        val  = f"  (value: {c['value']})" if c["value"] is not None else ""
        print(f"    {mark}  {c['name']}{val}")
        if not c["pass"]: all_ok = False

    print("\n" + "=" * 70)
    if all_ok:
        print("G-EVAL: ALL CHECKS PASSED — scoring is consistent and discriminative.")
        return 0
    print("G-EVAL: FAILURES DETECTED — see above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
