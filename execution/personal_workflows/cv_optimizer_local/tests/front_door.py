"""Front-door synthetic for cv_optimizer_local — per ~/.claude/rules/front-door-synthetic.md.

Exercises the actual user flow end-to-end:
  - Real CV PDF (fixtures/cv_en.pdf) -> pypdf extract
  - Real JD text (fixtures/jd_en.txt)
  - claude --print via operator's Claude subscription
  - JSON validation
  - HTML render -> A4 PDF + PNG via Playwright

Returns 0 on success, non-zero on any failure with a diagnostic.

Usage:
  py tests/front_door.py                 # one run
  py tests/front_door.py --runs 5        # N consecutive runs (target for "working" claim)
  py tests/front_door.py --quick         # --no-render (skip Playwright, faster)
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
CLI = PROJECT_ROOT / "cli.py"
FIXTURES = HERE / "fixtures"
CV_PDF = FIXTURES / "cv_en.pdf"
JD_TXT = FIXTURES / "jd_en.txt"

REQUIRED_FIELDS = (
    "language_detected", "ats_score", "name", "title", "contact",
    "summary", "experience", "skills", "education", "recommendations",
)


def fail(msg: str) -> int:
    print(f"[front-door] FAIL: {msg}", flush=True)
    return 1


def ok(msg: str):
    print(f"[front-door] {msg}", flush=True)


def run_once(quick: bool) -> int:
    if not CV_PDF.exists():
        return fail(f"fixture missing: {CV_PDF}")
    if not JD_TXT.exists():
        return fail(f"fixture missing: {JD_TXT}")
    if not CLI.exists():
        return fail(f"CLI missing: {CLI}")

    out_dir = HERE / "out" / time.strftime("%Y%m%d-%H%M%S")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    cmd = [
        "py", str(CLI),
        "--cv", str(CV_PDF),
        "--jd-text-file", str(JD_TXT),
        "--out-dir", str(out_dir),
    ]
    if quick:
        cmd.append("--no-render")

    t0 = time.time()
    r = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        shell=True, timeout=300,
    )
    dt = time.time() - t0
    if r.returncode != 0:
        return fail(f"CLI exit {r.returncode} after {dt:.1f}s; stderr={(r.stderr or '')[-300:]}")
    ok(f"CLI exited 0 in {dt:.1f}s")

    spec_path = out_dir / "cvspec.json"
    if not spec_path.exists():
        return fail(f"missing artifact: cvspec.json")
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return fail(f"cvspec.json not valid JSON: {exc}")

    missing = [f for f in REQUIRED_FIELDS if f not in spec]
    if missing:
        return fail(f"cvspec missing fields: {missing}")

    if spec.get("language_detected") != "en":
        return fail(f"language_detected={spec.get('language_detected')!r} expected 'en'")

    ats = spec.get("ats_score")
    if not isinstance(ats, int) or ats < 50 or ats > 100:
        return fail(f"ats_score out of expected range: {ats!r}")

    recs = spec.get("recommendations", [])
    if not isinstance(recs, list) or len(recs) < 3:
        return fail(f"recommendations missing or thin: {recs!r}")

    exp = spec.get("experience", [])
    if not exp or not isinstance(exp, list):
        return fail("experience empty")
    first_bullets = (exp[0] or {}).get("bullets", [])
    if not first_bullets:
        return fail("first experience entry has no bullets")

    # Profile enrichment indirect check (CLI doesn't fetch profile, but the prompt + LLM
    # may surface GitHub repos from the CV text if they're mentioned there).
    haystack = json.dumps(spec, ensure_ascii=False).lower()
    known_repos = ["anneal", "humanizer", "youtube"]
    repo_hits = [r for r in known_repos if r in haystack]
    if not repo_hits:
        # Non-fatal — the CV PDF may not mention these. Warn only.
        print(f"[front-door] WARN: no known GitHub repos surfaced in output")
    else:
        ok(f"GitHub repo surfaces in output: {repo_hits}")

    if not quick:
        for art in ("cv.html", "cv.pdf", "cv.png"):
            p = out_dir / art
            if not p.exists():
                return fail(f"render artifact missing: {art}")
            size = p.stat().st_size
            min_size = 5_000 if art != "cv.html" else 2_000
            if size < min_size:
                return fail(f"render artifact too small: {art} = {size}B (min {min_size}B)")
        ok(f"render artifacts present: html/pdf/png in {out_dir.name}")

    ok(f"PASS lang={spec['language_detected']} ats={ats} recs={len(recs)} exp_bullets[0]={len(first_bullets)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--quick", action="store_true", help="skip render (no Playwright)")
    args = parser.parse_args()

    failures = 0
    for i in range(args.runs):
        print(f"\n=== Run {i+1}/{args.runs} ===")
        rc = run_once(args.quick)
        if rc != 0:
            failures += 1
            print(f"[front-door] run {i+1} failed; aborting further runs.")
            break

    if failures == 0:
        print(f"\n[front-door] all {args.runs} run(s) PASS")
        return 0
    print(f"\n[front-door] {failures}/{args.runs} runs FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
