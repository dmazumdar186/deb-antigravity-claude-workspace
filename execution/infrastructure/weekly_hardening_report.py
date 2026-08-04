"""
weekly_hardening_report.py
description: Regenerates the workspace-level HARDENING report. Runs SAST, freshness_monitor, samples recent commits for shipped-claim phrasing, and writes HARDENING_BACKLOG_WORKSPACE_<YYYY-MM-DD>.md at the workspace root. Prior reports stay as an audit trail. No LLM calls.
inputs: --out (default: workspace root), --commits (default: 200), --since-days (default: 14). Env: none.
outputs: A single Markdown file HARDENING_BACKLOG_WORKSPACE_<date>.md and a stdout summary. Exit code 0 (report generated), 1 (any critical section failed), 2 (workspace root not detected).

Wired into a Monday morning cadence via either:
  (a) local runbook — operator runs `py execution/infrastructure/weekly_hardening_report.py`
  (b) GitHub Actions cron (weekly, Mondays at 07:00 UTC)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SAST_SCRIPT = WORKSPACE_ROOT / "execution" / "infrastructure" / "workspace_sast.py"
FRESHNESS_SCRIPT = WORKSPACE_ROOT / "execution" / "infrastructure" / "freshness_monitor.py"

# Forbidden framings — mirrors panel-pass.md's list.  Matched case-insensitively
# with word boundaries so we don't false-flag things like "readiness" or
# "workshopped".
FORBIDDEN_FRAMINGS = (
    r"\bshipped\b",
    r"\bshipping\b",
    r"\blive\b",
    r"\bready\b",
    r"\bdone\b",
    r"\bcomplete(?:d)?\b",
    r"\bwrapped\b",
    r"100% ?complete",
    r"\bgood to go\b",
    r"\ball set\b",
    r"\bsorted\b",
)
_SHIPPED_RE = re.compile("|".join(FORBIDDEN_FRAMINGS), re.IGNORECASE)


def _run(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str, str]:
    """Run a subprocess; return (returncode, stdout, stderr). UTF-8 safe on Windows."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as err:
        return 124, "", f"timeout after {timeout}s: {err}"
    except FileNotFoundError as err:
        return 127, "", f"command not found: {err}"
    return proc.returncode, proc.stdout, proc.stderr


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _run_sast(level: str = "high") -> dict:
    if not SAST_SCRIPT.exists():
        return {"available": False, "error": f"SAST script missing at {SAST_SCRIPT}"}
    rc, out, err = _run(
        [sys.executable, str(SAST_SCRIPT), f"--level={level}"],
        cwd=WORKSPACE_ROOT,
        timeout=300,
    )
    return {
        "available": True,
        "exit_code": rc,
        "stdout_tail": out[-4000:],
        "stderr_tail": err[-2000:],
    }


def _run_freshness() -> dict:
    if not FRESHNESS_SCRIPT.exists():
        return {"available": False, "error": f"freshness_monitor missing at {FRESHNESS_SCRIPT}"}
    rc, out, err = _run(
        [sys.executable, str(FRESHNESS_SCRIPT), "--format=json", "--level=info"],
        cwd=WORKSPACE_ROOT,
        timeout=60,
    )
    try:
        report = json.loads(out) if out.strip() else {}
    except json.JSONDecodeError:
        report = {}
    return {
        "available": True,
        "exit_code": rc,
        "report": report,
        "stderr_tail": err[-2000:],
    }


def _sample_commits(n: int, since_days: int) -> dict:
    rc, out, err = _run(
        [
            "git",
            "log",
            f"--since={since_days}.days.ago",
            f"-n{n}",
            "--pretty=format:%h %cI %s",
        ],
        cwd=WORKSPACE_ROOT,
        timeout=30,
    )
    if rc != 0:
        return {"available": False, "error": err.strip()[:400]}

    matches: list[dict] = []
    total = 0
    for line in out.splitlines():
        if not line.strip():
            continue
        total += 1
        m = _SHIPPED_RE.search(line)
        if m:
            matches.append({"line": line, "matched": m.group(0)})
    return {
        "available": True,
        "total_commits": total,
        "since_days": since_days,
        "shipped_claim_count": len(matches),
        "shipped_claim_rate": round(len(matches) / total, 3) if total else 0.0,
        "matches_head": matches[:20],
    }


def _detect_untracked_pages_functions() -> dict:
    """List every .ts/.tsx/.js/.mjs file inside any functions/ directory that is untracked in git."""
    rc, out, err = _run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=WORKSPACE_ROOT,
        timeout=30,
    )
    if rc != 0:
        return {"available": False, "error": err.strip()[:400]}
    hits: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # Cross-platform: normalise separators.
        norm = line.replace("\\", "/")
        if "/functions/" in norm and norm.endswith((".ts", ".tsx", ".js", ".mjs", ".jsx")):
            hits.append(line)
    return {"available": True, "untracked_pages_function_count": len(hits), "hits": hits}


def _render_report(bundle: dict) -> str:
    lines: list[str] = []
    date = bundle["generated_at"][:10]
    lines.append(f"# Workspace HARDENING report - {date}")
    lines.append("")
    lines.append(
        f"Auto-generated by `execution/infrastructure/weekly_hardening_report.py` at {bundle['generated_at']}.",
    )
    lines.append(
        "Prior reports stay in the workspace root as an audit trail. This file is regenerated weekly; the previous week's file is not modified.",
    )
    lines.append("")

    # --- Section 1: SAST -----------------------------------------------------
    lines.append("## 1. Workspace SAST (--level=high)")
    lines.append("")
    sast = bundle["sast"]
    if not sast.get("available"):
        lines.append(f"SAST unavailable: {sast.get('error')}")
    else:
        rc = sast["exit_code"]
        verdict = "PASS" if rc == 0 else "FAIL"
        lines.append(f"Exit code: **{rc}** ({verdict})")
        lines.append("")
        if sast.get("stdout_tail", "").strip():
            lines.append("```")
            lines.append(sast["stdout_tail"].strip())
            lines.append("```")
    lines.append("")

    # --- Section 2: Freshness ------------------------------------------------
    lines.append("## 2. Freshness (per-project)")
    lines.append("")
    fr = bundle["freshness"]
    if not fr.get("available"):
        lines.append(f"freshness_monitor unavailable: {fr.get('error')}")
    else:
        report = fr.get("report") or {}
        summary = report.get("summary", {})
        lines.append(
            f"OK={summary.get('ok', 0)} - DEGRADED={summary.get('degraded', 0)} - NO_SIGNAL={summary.get('no_signal', 0)} - INFO_ONLY={summary.get('info_only', 0)}",
        )
        lines.append("")
        lines.append("| Slug | Type | Verdict | Age (h) | Threshold (h) | Reason |")
        lines.append("|---|---|---|---|---|---|")
        for row in report.get("projects", []):
            lines.append(
                "| {slug} | {type} | **{verdict}** | {age} | {threshold} | {reason} |".format(
                    slug=row.get("slug", ""),
                    type=row.get("type", ""),
                    verdict=row.get("verdict", ""),
                    age="-" if row.get("combined_age_hours") is None else row["combined_age_hours"],
                    threshold="-" if row.get("threshold_hours") is None else row["threshold_hours"],
                    reason=(row.get("reason") or "").replace("|", "/"),
                ),
            )
    lines.append("")

    # --- Section 3: Commit sampling -----------------------------------------
    commits = bundle["commits"]
    lines.append("## 3. Shipped-claim discipline (commit sampling)")
    lines.append("")
    if not commits.get("available"):
        lines.append(f"commit sampling unavailable: {commits.get('error')}")
    else:
        rate = commits["shipped_claim_rate"]
        lines.append(
            f"Sampled last **{commits['total_commits']}** commits over **{commits['since_days']} days**. "
            f"Shipped-claim mentions: **{commits['shipped_claim_count']}** (rate={rate}).",
        )
        lines.append("")
        if commits["matches_head"]:
            lines.append("Sample matches (head 20):")
            lines.append("")
            for m in commits["matches_head"]:
                safe_line = m["line"].replace("|", "/")
                lines.append(f"- `{m['matched']}` in `{safe_line}`")
        else:
            lines.append("No forbidden framings detected in recent commits.")
    lines.append("")

    # --- Section 4: Untracked Pages Functions -------------------------------
    lines.append("## 4. Pattern A guardrail (untracked functions/ files)")
    lines.append("")
    upf = bundle["untracked_pages_functions"]
    if not upf.get("available"):
        lines.append(f"guardrail unavailable: {upf.get('error')}")
    else:
        n = upf["untracked_pages_function_count"]
        lines.append(f"Untracked function-tree source files: **{n}**")
        if n > 0:
            lines.append("")
            for hit in upf["hits"][:50]:
                lines.append(f"- `{hit}`")
            if len(upf["hits"]) > 50:
                lines.append(f"- ...and {len(upf['hits']) - 50} more")
    lines.append("")

    # --- Section 5: How to act ----------------------------------------------
    lines.append("## 5. Recommended next actions")
    lines.append("")
    lines.append(
        "1. Any **DEGRADED** row above needs a look — either the cron is stopped, the health probe is wrong, or the project is truly abandoned (retype to `interactive_only`).",
    )
    lines.append(
        "2. Any **untracked function-tree file** should be `git add`ed or deleted before the next `wrangler pages deploy` — this is the exact 2026-07-21 yoga_jitendra fault pattern.",
    )
    lines.append(
        "3. Any commit-message row with a forbidden framing (`shipped`, `done`, etc.) should have a paired verdict-table entry — check the corresponding HANDOFF / session log.",
    )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*Generated read-only; no fixes applied. Regenerate: `py execution/infrastructure/weekly_hardening_report.py`.*",
    )
    return "\n".join(lines) + "\n"


def build_bundle(commits_n: int, since_days: int) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sast": _run_sast(level="high"),
        "freshness": _run_freshness(),
        "commits": _sample_commits(n=commits_n, since_days=since_days),
        "untracked_pages_functions": _detect_untracked_pages_functions(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Weekly workspace HARDENING report generator.")
    parser.add_argument("--out", type=Path, default=WORKSPACE_ROOT, help="Output directory (default: workspace root).")
    parser.add_argument("--commits", type=int, default=200)
    parser.add_argument("--since-days", type=int, default=14)
    args = parser.parse_args(argv)

    if not (WORKSPACE_ROOT / "CLAUDE.md").exists():
        print(f"workspace root not detected (no CLAUDE.md at {WORKSPACE_ROOT})", file=sys.stderr)
        return 2

    bundle = build_bundle(commits_n=args.commits, since_days=args.since_days)
    body = _render_report(bundle)

    out_path = args.out / f"HARDENING_BACKLOG_WORKSPACE_{_today_iso()}.md"
    args.out.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")

    print(f"weekly_hardening_report: wrote {out_path}")
    print(
        f"  SAST exit={bundle['sast'].get('exit_code')} "
        f"freshness_degraded={((bundle['freshness'].get('report') or {}).get('summary') or {}).get('degraded', 'n/a')} "
        f"untracked_functions={bundle['untracked_pages_functions'].get('untracked_pages_function_count', 'n/a')}",
    )

    return 0 if bundle["sast"].get("exit_code", 1) in (0, None) else 1


if __name__ == "__main__":
    sys.exit(main())
