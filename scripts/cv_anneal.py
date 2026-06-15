"""
description: Self-iterative audit-loop driver for the CV rewrite.
inputs:
  --lang fr|en  : run one language (default: both)
  --max-iters N : cap iterations (default 6)
  --pass-on-ats : terminate as soon as ATS audit passes, even if panel isn't run
outputs:
  - .tmp/cv_anneal/<lang>_round<N>/{summary.json, ats_findings.json, panel.json}
  - per-round verdict (CLEAN / NEEDS_REVISION) printed to stdout
  - Final PDFs at .tmp/cv_master_debanjan_mazumdar{,_en}.pdf

Loop:
  Round N:
    1. py execution/personal_workflows/cv_builder.py (FR) and _en.py
    2. py tests/cv_ats_check.py --lang fr and --lang en
    3. py tests/cv_recruiter_panel.py --pdf <pdf> --lang <lang>
    4. If both clean → CLEAN ROUND; else → record findings, log mutation hint.
  Terminate on 2 consecutive CLEAN rounds OR after max_iters.

Mutation is intentionally manual in this iteration: this driver reports findings
and the operator (you) decides whether to patch build_story() and re-run. The
driver does NOT auto-mutate Python source (that would mask drift). Instead, each
round writes a concrete TODO list for what to patch.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("cv_anneal")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANNEAL_DIR = PROJECT_ROOT / ".tmp" / "cv_anneal"


def run(cmd: list[str], cwd: Path = PROJECT_ROOT) -> tuple[int, str, str]:
    """Run a subprocess with cp1252-safe encoding."""
    proc = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True,
        encoding="utf-8", errors="replace", timeout=600,
    )
    return proc.returncode, proc.stdout, proc.stderr


def render(lang: str) -> tuple[int, Path]:
    script = (
        "execution/personal_workflows/cv_builder.py" if lang == "fr"
        else "execution/personal_workflows/cv_builder_en.py"
    )
    rc, _, err = run(["py", script, "--company", "master", "--role", "AI Product Manager"])
    pdf = PROJECT_ROOT / ".tmp" / (
        "cv_master_debanjan_mazumdar.pdf" if lang == "fr"
        else "cv_master_debanjan_mazumdar_en.pdf"
    )
    if rc != 0:
        logger.error("render(%s) failed: %s", lang, err[:500])
    return rc, pdf


def ats_check(pdf: Path, lang: str) -> tuple[int, dict]:
    rc, out, _ = run(["py", "tests/cv_ats_check.py", "--pdf", str(pdf), "--lang", lang])
    findings = [l.strip("- ").strip() for l in out.splitlines() if l.startswith("  - ")]
    pages_line = next((l for l in out.splitlines() if "Pages" in l), "")
    keywords_line = next((l for l in out.splitlines() if "ATS keyword hits" in l), "")
    metrics_line = next((l for l in out.splitlines() if "Quantified metrics" in l), "")
    return rc, {
        "rc": rc, "findings": findings,
        "pages_line": pages_line.strip(),
        "keywords_line": keywords_line.strip(),
        "metrics_line": metrics_line.strip(),
    }


def panel(pdf: Path, lang: str) -> tuple[int, dict]:
    rc, out, _ = run(["py", "tests/cv_recruiter_panel.py", "--pdf", str(pdf), "--lang", lang])
    json_path = (
        PROJECT_ROOT / ".tmp" / "cv_recruiter_panel" / f"{pdf.stem}.json"
    )
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"summary": {"pass": False, "_parse_error": True}}
    else:
        data = {"summary": {"pass": False, "_no_output": True}, "raw_stdout": out[-2000:]}
    return rc, data


def one_round(lang: str, round_num: int, run_panel: bool) -> dict:
    round_dir = ANNEAL_DIR / f"{lang}_round{round_num}"
    round_dir.mkdir(parents=True, exist_ok=True)

    rc_render, pdf = render(lang)
    if rc_render != 0:
        return {"lang": lang, "round": round_num, "clean": False, "phase": "render_failed"}

    rc_ats, ats_result = ats_check(pdf, lang)
    (round_dir / "ats_findings.json").write_text(json.dumps(ats_result, indent=2), encoding="utf-8")

    if not run_panel:
        return {
            "lang": lang, "round": round_num,
            "clean": rc_ats == 0,
            "phase": "ats_only",
            "ats": ats_result,
        }

    rc_panel, panel_result = panel(pdf, lang)
    (round_dir / "panel.json").write_text(json.dumps(panel_result, indent=2, ensure_ascii=False), encoding="utf-8")
    panel_summary = panel_result.get("summary", {})

    clean = (rc_ats == 0) and bool(panel_summary.get("pass", False))
    return {
        "lang": lang, "round": round_num, "clean": clean,
        "ats_ok": rc_ats == 0,
        "panel_ok": bool(panel_summary.get("pass", False)),
        "ats_findings": ats_result.get("findings", []),
        "panel_summary": panel_summary,
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Self-iterative CV audit loop")
    parser.add_argument("--lang", choices=["fr", "en", "both"], default="both")
    parser.add_argument("--max-iters", type=int, default=6)
    parser.add_argument("--pass-on-ats", action="store_true",
                        help="Terminate when ATS audit passes; skip panel (use when quota is exhausted)")
    args = parser.parse_args()

    langs = ["fr", "en"] if args.lang == "both" else [args.lang]
    ANNEAL_DIR.mkdir(parents=True, exist_ok=True)

    history = {l: [] for l in langs}
    consecutive_clean = {l: 0 for l in langs}
    done = {l: False for l in langs}

    for round_num in range(1, args.max_iters + 1):
        for lang in langs:
            if done[lang]:
                continue
            logger.info("=== Round %d (%s) ===", round_num, lang)
            result = one_round(lang, round_num, run_panel=not args.pass_on_ats)
            history[lang].append(result)
            if result["clean"]:
                consecutive_clean[lang] += 1
                logger.info("Round %d %s: CLEAN (%d consecutive)", round_num, lang, consecutive_clean[lang])
                if consecutive_clean[lang] >= 2:
                    done[lang] = True
            else:
                consecutive_clean[lang] = 0
                logger.info("Round %d %s: NEEDS_REVISION — ats=%s panel=%s",
                            round_num, lang,
                            result.get("ats_ok"), result.get("panel_ok"))
                if result.get("ats_findings"):
                    for f in result["ats_findings"]:
                        logger.info("  ats: %s", f)
                if "panel_summary" in result and result["panel_summary"].get("mutation_hint"):
                    logger.info("  panel mutation_hint: %s", result["panel_summary"]["mutation_hint"])

        if all(done.values()):
            logger.info("All languages converged. Exiting.")
            break

    summary = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "languages": langs,
        "consecutive_clean": consecutive_clean,
        "done": done,
        "history": history,
    }
    (ANNEAL_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSummary written to {ANNEAL_DIR / 'summary.json'}")
    for lang in langs:
        print(f"  {lang}: done={done[lang]} consecutive_clean={consecutive_clean[lang]}")
    return 0 if all(done.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
