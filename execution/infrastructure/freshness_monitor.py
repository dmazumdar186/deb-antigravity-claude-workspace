"""
freshness_monitor.py
description: Reads workspace_heartbeat/manifest.json and reports git-log + run-log freshness per project. Detects Pattern B (shipped claims surviving month-long silence) locally. No LLM calls, no network calls — pure git + filesystem.
inputs: --manifest (default: execution/infrastructure/workspace_heartbeat/manifest.json), --level {info,warn,fail}, --format {json,markdown,human}. Env: none.
outputs: JSON/Markdown/human report to stdout. Exit code 0 (all fresh), 1 (any DEGRADED at --level=warn/fail), 2 (manifest error).

Freshness logic per project:
  * cron_*  : max(git-log HEAD age on git_path, run_log age)  vs freshness_threshold_hours
  * interactive_only: git-log HEAD age on git_path vs freshness_threshold_hours (default 1440h = 60d)
  * pages_site: git-log HEAD age on git_path — no threshold (informational only)

Wired into pre-push via .githooks/pre-push (WARN level, non-blocking).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = (
    WORKSPACE_ROOT
    / "execution"
    / "infrastructure"
    / "workspace_heartbeat"
    / "manifest.json"
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _git_last_commit_age_hours(repo_root: Path, path: str) -> tuple[float | None, str | None]:
    """Return (age_in_hours, iso_last_commit) for the newest commit touching `path`.

    Returns (None, None) if the path has never been committed (untracked or new).
    """
    target = repo_root / path
    if not target.exists():
        return None, None

    try:
        # %cI = strict ISO 8601 committer date.
        # -- <path> restricts log to commits touching that path.
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as err:
        return None, f"git-log failed: {err}"

    if result.returncode != 0:
        return None, f"git-log exit {result.returncode}: {result.stderr.strip()[:200]}"

    iso = result.stdout.strip()
    if not iso:
        return None, None

    try:
        ts = datetime.fromisoformat(iso)
    except ValueError:
        return None, f"unparseable git ISO: {iso}"

    age_h = (_now_utc() - ts).total_seconds() / 3600.0
    return age_h, iso


def _run_log_last_age_hours(repo_root: Path, path: str | None) -> tuple[float | None, str | None]:
    """Read the last line of a JSONL run log; return (age_h, iso). None if absent."""
    if not path:
        return None, None
    log = repo_root / path
    if not log.exists() or not log.is_file():
        return None, None
    try:
        # For large files, avoid slurping the whole thing — read last 4KB.
        size = log.stat().st_size
        with log.open("rb") as fh:
            fh.seek(max(0, size - 4096))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError as err:
        return None, f"run-log read failed: {err}"

    last = None
    for line in tail.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue

    if not last:
        return None, None

    # Accept common timestamp field names.
    iso = None
    for key in ("ended_at", "finished_at", "completed_at", "run_at", "started_at", "timestamp", "time"):
        if isinstance(last.get(key), str):
            iso = last[key]
            break
    if not iso:
        return None, None

    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None, f"unparseable run-log ISO: {iso}"

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    age_h = (_now_utc() - ts).total_seconds() / 3600.0
    return age_h, iso


def _classify(project: dict, git_age: float | None, run_log_age: float | None) -> dict:
    """Compute the verdict for a single project."""
    ptype = project.get("type", "unknown")
    threshold = project.get("freshness_threshold_hours")

    # Combine signals: use the freshest of git-log + run-log (freshest = smallest age).
    ages = [a for a in (git_age, run_log_age) if a is not None]
    combined_age = min(ages) if ages else None

    verdict = "OK"
    reason = None

    if ptype == "pages_site":
        # No cron; git-log is informational. Never DEGRADED from this monitor.
        # (Live-URL DEGRADED is the Worker's job.)
        verdict = "INFO_ONLY"
    elif combined_age is None:
        verdict = "NO_SIGNAL"
        reason = "no git-log and no run-log found"
    elif threshold is None:
        verdict = "OK"
        reason = "no threshold declared; skipping freshness check"
    elif combined_age > threshold:
        verdict = "DEGRADED"
        reason = f"age {combined_age:.1f}h > threshold {threshold}h"

    return {
        "slug": project.get("slug"),
        "type": ptype,
        "git_age_hours": None if git_age is None else round(git_age, 1),
        "run_log_age_hours": None if run_log_age is None else round(run_log_age, 1),
        "combined_age_hours": None if combined_age is None else round(combined_age, 1),
        "threshold_hours": threshold,
        "verdict": verdict,
        "reason": reason,
    }


def _load_manifest(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _render_human(report: dict) -> str:
    lines = []
    lines.append(f"freshness_monitor @ {report['generated_at']}")
    lines.append(f"  workspace_root: {report['workspace_root']}")
    lines.append(f"  manifest:       {report['manifest_path']}")
    summary = report["summary"]
    lines.append(
        f"  totals: OK={summary['ok']}  DEGRADED={summary['degraded']}  NO_SIGNAL={summary['no_signal']}  INFO_ONLY={summary['info_only']}",
    )
    lines.append("")
    for row in report["projects"]:
        marker = {
            "OK": "  ok",
            "DEGRADED": "  !!",
            "NO_SIGNAL": "  ??",
            "INFO_ONLY": "  --",
        }.get(row["verdict"], "  ??")
        detail_bits = [f"type={row['type']}"]
        if row["combined_age_hours"] is not None:
            detail_bits.append(f"age={row['combined_age_hours']}h")
        if row["threshold_hours"] is not None:
            detail_bits.append(f"threshold={row['threshold_hours']}h")
        if row["reason"]:
            detail_bits.append(f"reason={row['reason']}")
        lines.append(f"{marker}  {row['verdict']:<10}  {row['slug']:<32}  {'  '.join(detail_bits)}")
    return "\n".join(lines)


def _render_markdown(report: dict) -> str:
    lines = []
    lines.append(f"# Freshness report ({report['generated_at']})")
    lines.append("")
    summary = report["summary"]
    lines.append(
        f"OK={summary['ok']} · DEGRADED={summary['degraded']} · NO_SIGNAL={summary['no_signal']} · INFO_ONLY={summary['info_only']}",
    )
    lines.append("")
    lines.append("| Slug | Type | Verdict | Age (h) | Threshold (h) | Reason |")
    lines.append("|---|---|---|---|---|---|")
    for row in report["projects"]:
        lines.append(
            "| {slug} | {type} | {verdict} | {age} | {threshold} | {reason} |".format(
                slug=row["slug"],
                type=row["type"],
                verdict=row["verdict"],
                age="-" if row["combined_age_hours"] is None else row["combined_age_hours"],
                threshold="-" if row["threshold_hours"] is None else row["threshold_hours"],
                reason=row["reason"] or "",
            ),
        )
    return "\n".join(lines) + "\n"


def build_report(manifest_path: Path) -> dict:
    manifest = _load_manifest(manifest_path)
    projects = manifest.get("projects", [])
    rows: list[dict] = []
    for project in projects:
        git_path = project.get("git_path")
        run_log_path = project.get("run_log_path")
        git_age, _git_iso = (None, None)
        if git_path:
            git_age, _git_iso = _git_last_commit_age_hours(WORKSPACE_ROOT, git_path)
        run_age, _run_iso = _run_log_last_age_hours(WORKSPACE_ROOT, run_log_path)
        rows.append(_classify(project, git_age, run_age))

    summary = {
        "ok": sum(1 for r in rows if r["verdict"] == "OK"),
        "degraded": sum(1 for r in rows if r["verdict"] == "DEGRADED"),
        "no_signal": sum(1 for r in rows if r["verdict"] == "NO_SIGNAL"),
        "info_only": sum(1 for r in rows if r["verdict"] == "INFO_ONLY"),
    }

    return {
        "generated_at": _now_utc().isoformat(),
        "workspace_root": str(WORKSPACE_ROOT),
        "manifest_path": str(manifest_path),
        "summary": summary,
        "projects": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report freshness per project vs manifest thresholds.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--level",
        choices=("info", "warn", "fail"),
        default="warn",
        help="info: never non-zero exit; warn: exit 1 on DEGRADED (default); fail: same as warn — kept for future WARN vs FAIL split.",
    )
    parser.add_argument("--format", choices=("json", "markdown", "human"), default="human")
    args = parser.parse_args(argv)

    if not args.manifest.exists():
        print(f"manifest not found: {args.manifest}", file=sys.stderr)
        return 2

    try:
        report = build_report(args.manifest)
    except (OSError, json.JSONDecodeError) as err:
        print(f"freshness_monitor failed: {err}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(_render_markdown(report))
    else:
        print(_render_human(report))

    if args.level == "info":
        return 0
    return 1 if report["summary"]["degraded"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
