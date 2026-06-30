"""
description: Unified test runner for the dental voice receptionist. Discovers tests in
tiered subdirectories (smoke, sanity, edge, negative) and runs them with a consistent
contract: each test is a Python module exposing run() -> dict {ok: bool, ...details}.
The runner aggregates results, prints a summary table, and exits 0 on all-PASS, 1 on
any FAIL. Mic-required tests (listen_test_*) are excluded; this runner is fully
headless / CI-safe.

inputs:
    --tier smoke|sanity|edge|negative|all  pick a tier (default: all)
    --pattern PATTERN                       filter tests by name substring
    --fail-fast                             stop after first failure
    --verbose                               print full test stdout / tracebacks

outputs:
    stdout: per-tier results table, then summary
    exit code: 0 all PASS, 1 any FAIL, 2 setup/discovery error

Tier conventions:
    SMOKE    -- fast (<5s), no external dependencies that can fail, "is it on?"
    SANITY   -- correctness checks on observable behavior, no LLM, no audio
    EDGE     -- boundary inputs (9/11 digits, empty calendar, foreign names)
    NEGATIVE -- error paths (invalid args, missing fields, 4xx/5xx upstream)

Per ~/.claude/rules/testing.md: this is the harness for the 6-tier test suite
adapted to a voice-agent shape. Performance + Monkey tiers run separately when
they make sense (mostly for outbound dialing campaigns, not relevant yet).
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
import traceback
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    # Best-effort stream reconfigure on platforms that don't support it.
    pass

ROOT = Path(__file__).resolve().parent
TIERS = ("smoke", "sanity", "edge", "negative")


def discover(tier: str, pattern: str | None) -> list[Path]:
    tier_dir = ROOT / tier
    if not tier_dir.is_dir():
        return []
    out = []
    for p in sorted(tier_dir.glob("*.py")):
        if p.name.startswith("_"):
            continue
        if pattern and pattern not in p.stem:
            continue
        out.append(p)
    return out


def run_test(path: Path, verbose: bool) -> dict:
    spec = importlib.util.spec_from_file_location(f"_t_{path.stem}", path)
    if not spec or not spec.loader:
        return {"ok": False, "error": "could not load module", "duration_s": 0.0}
    mod = importlib.util.module_from_spec(spec)
    t0 = time.time()
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"import error: {exc.__class__.__name__}: {exc}",
            "duration_s": time.time() - t0,
            "traceback": traceback.format_exc() if verbose else None,
        }
    if not hasattr(mod, "run"):
        return {"ok": False, "error": "no run() function defined", "duration_s": 0.0}
    try:
        result = mod.run()
    except Exception as exc:
        return {
            "ok": False,
            "error": f"runtime error: {exc.__class__.__name__}: {exc}",
            "duration_s": time.time() - t0,
            "traceback": traceback.format_exc() if verbose else None,
        }
    duration = time.time() - t0
    if not isinstance(result, dict):
        return {"ok": False, "error": f"run() returned {type(result).__name__}, not dict",
                "duration_s": duration}
    result.setdefault("ok", False)
    result["duration_s"] = duration
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", choices=("smoke", "sanity", "edge", "negative", "all"),
                    default="all")
    ap.add_argument("--pattern", help="filter tests by name substring")
    ap.add_argument("--fail-fast", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    tiers = TIERS if args.tier == "all" else (args.tier,)

    grand_pass = grand_fail = 0
    grand_t0 = time.time()

    for tier in tiers:
        tests = discover(tier, args.pattern)
        if not tests:
            print(f"\n=== {tier.upper()} (no tests found) ===")
            continue

        print(f"\n=== {tier.upper()} ({len(tests)} tests) ===")
        tier_pass = tier_fail = 0
        for p in tests:
            res = run_test(p, args.verbose)
            status = "PASS" if res.get("ok") else "FAIL"
            dur = res.get("duration_s", 0.0)
            detail = ""
            if not res.get("ok"):
                detail = res.get("error", "")
                if not detail and "summary" in res:
                    detail = str(res["summary"])
            elif args.verbose and "summary" in res:
                detail = str(res["summary"])
            print(f"  {status}  {p.stem:<40} {dur:.2f}s  {detail[:120]}")
            if args.verbose and res.get("traceback"):
                print("    " + res["traceback"].replace("\n", "\n    "))
            if res.get("ok"):
                tier_pass += 1
                grand_pass += 1
            else:
                tier_fail += 1
                grand_fail += 1
                if args.fail_fast:
                    print(f"\n--fail-fast: stopping after {p.stem}")
                    print(f"summary: {grand_pass} PASS / {grand_fail} FAIL "
                          f"(elapsed {time.time() - grand_t0:.1f}s)")
                    return 1
        print(f"  -- {tier} subtotal: {tier_pass} PASS / {tier_fail} FAIL")

    elapsed = time.time() - grand_t0
    print(f"\nsummary: {grand_pass} PASS / {grand_fail} FAIL  (elapsed {elapsed:.1f}s)")
    return 0 if grand_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
