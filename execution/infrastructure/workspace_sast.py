"""Workspace SAST pre-pass runner.

Runs ruff and semgrep over Python files in execution/ and surfaces findings
as a markdown report.  Designed to run as a Claude Code PostToolUse hook
(warn-mode) or manually before PRs.

Plan ref: ~/.claude/plans/i-need-to-write-bubbly-pelican.md (Tier 3)
Architecture ref: CLAUDE.md — 3-layer directives/execution/orchestration

Exit codes:
    0 — no critical or high findings (or no tools installed but files scanned)
    1 — at least one critical or high finding found
    2 — neither ruff nor semgrep is installed
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Semgrep on Windows Python 3.14 calls Path.home() which raises
# RuntimeError when neither HOME nor USERPROFILE is set (e.g. in
# restricted hook subprocess contexts). Establish a fallback early so
# both the anneal-import path and the subprocess-fallback path see it.
if not os.environ.get("HOME") and not os.environ.get("USERPROFILE"):
    _fallback = tempfile.gettempdir()
    os.environ["HOME"] = _fallback
    if os.name == "nt":
        os.environ["USERPROFILE"] = _fallback

# ── Workspace root ───────────────────────────────────────────────────────────
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
ANNEAL_SRC = Path("C:/Users/deban/dev/anneal/src")

# ── AM-lockdown patterns (case-insensitive) ──────────────────────────────────
_AM_PATTERNS = ("accessory", "hedgestone", "elite-broker", "elitebrokergroup")

# ── Directories to skip when walking execution/ ──────────────────────────────
_SKIP_DIRS = {".venv", "__pycache__", ".tmp", "node_modules", ".git", "modules"}

# ── Severity ordering ────────────────────────────────────────────────────────
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


# ── AM-lockdown guard ────────────────────────────────────────────────────────

def _is_am_locked(path: str) -> bool:
    """Return True if the path matches any AM-lockdown pattern."""
    lower = path.lower()
    return any(pat in lower for pat in _AM_PATTERNS)


# ── Anneal import (try-first) ────────────────────────────────────────────────

def _try_anneal_import():
    """Attempt to import anneal's SAST runners.  Returns (CompositeSastRunner, RuffRunner,
    SemgrepRunner, SastFinding) or None on failure."""
    if ANNEAL_SRC.exists():
        sys.path.insert(0, str(ANNEAL_SRC))
    try:
        from anneal.sast.composite import CompositeSastRunner  # type: ignore
        from anneal.sast.ruff_runner import RuffRunner  # type: ignore
        from anneal.sast.semgrep_runner import SemgrepRunner  # type: ignore
        from anneal.sast.base import SastFinding  # type: ignore

        return CompositeSastRunner, RuffRunner, SemgrepRunner, SastFinding
    except ImportError:
        return None


# ── Subprocess fallback ──────────────────────────────────────────────────────

def _map_ruff_severity(rule_id: str) -> str:
    if not rule_id:
        return "info"
    prefix = rule_id[0].upper()
    if prefix == "S":
        return "high"
    if prefix in ("E", "W"):
        return "medium"
    if prefix == "F":
        return "low"
    return "info"


def _map_semgrep_severity(severity: str) -> str:
    mapping = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}
    return mapping.get(severity.upper(), "info")


def _run_ruff_fallback(files: list[str]) -> list[dict]:
    """Run ruff via subprocess.  Returns list of finding dicts."""
    import shutil

    if not shutil.which("ruff"):
        return []
    cmd = ["ruff", "check", "--output-format=json", "--no-cache", "--", *files]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    if result.returncode >= 2:
        return []

    try:
        data = json.loads(result.stdout.strip() or "[]")
    except json.JSONDecodeError:
        return []

    findings = []
    for item in data:
        rule_id = item.get("code") or ""
        location = item.get("location") or {}
        findings.append(
            {
                "severity": _map_ruff_severity(rule_id),
                "file": item.get("filename") or "",
                "line": int(location.get("row", 0)),
                "rule_id": rule_id,
                "message": item.get("message") or "",
                "tool": "ruff",
            }
        )
    return findings


def _run_semgrep_fallback(files: list[str]) -> list[dict]:
    """Run semgrep via subprocess.  Returns list of finding dicts."""
    import shutil

    if not shutil.which("semgrep"):
        return []
    cmd = ["semgrep", "scan", "--json", "--quiet", "--config=auto", *files]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    try:
        data = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return []

    findings = []
    for item in data.get("results", []):
        sev_raw = item.get("extra", {}).get("severity", "INFO")
        path = item.get("path") or ""
        start = item.get("start") or {}
        findings.append(
            {
                "severity": _map_semgrep_severity(sev_raw),
                "file": path,
                "line": int(start.get("line", 0)),
                "rule_id": item.get("check_id") or "",
                "message": (item.get("extra") or {}).get("message") or "",
                "tool": "semgrep",
            }
        )
    return findings


# ── File collection ──────────────────────────────────────────────────────────

def _collect_changed_files() -> list[Path]:
    """Return .py files in execution/ that are changed vs HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=WORKSPACE_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            encoding="utf-8",
            errors="replace",
        )
        changed = result.stdout.strip().splitlines()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        changed = []

    paths = []
    for rel in changed:
        if not rel.endswith(".py"):
            continue
        if not rel.startswith("execution/") and not rel.startswith("execution\\"):
            continue
        if _is_am_locked(rel):
            continue
        full = WORKSPACE_ROOT / rel
        if full.exists():
            paths.append(full)
    return paths


def _collect_all_files() -> list[Path]:
    """Walk execution/**/*.py skipping excluded dirs and AM-locked paths."""
    base = WORKSPACE_ROOT / "execution"
    paths = []
    for p in base.rglob("*.py"):
        # Skip excluded dirs
        parts = set(p.parts)
        if any(skip in parts for skip in _SKIP_DIRS):
            continue
        if _is_am_locked(str(p)):
            continue
        paths.append(p)
    return paths


# ── Markdown report ──────────────────────────────────────────────────────────

def _render_report(findings: list[dict], n_scanned: int, quiet: bool = False) -> str:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    total = sum(counts.values())
    header = (
        "## Workspace SAST report\n"
        f"Scanned: {n_scanned} files\n"
        f"Findings: {total} (critical: {counts['critical']}, high: {counts['high']}, "
        f"medium: {counts['medium']}, low: {counts['low']})\n"
    )

    if quiet and total == 0:
        return ""

    lines = [header]
    sorted_findings = sorted(findings, key=lambda x: _SEVERITY_ORDER.get(x["severity"], 99))
    for f in sorted_findings:
        lines.append(
            f"\n### {f['severity']} — {f['file']}:{f['line']} [{f['tool']}:{f['rule_id']}]"
        )
        lines.append(f["message"])

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Workspace SAST pre-pass (ruff + semgrep)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--changed", action="store_true", default=True,
                      help="Scan changed .py files in execution/ vs HEAD (default)")
    mode.add_argument("--all", dest="all_files", action="store_true",
                      help="Scan all execution/**/*.py")
    mode.add_argument("--files", nargs="+", metavar="FILE",
                      help="Scan explicit file paths")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress output when there are no findings")
    args = parser.parse_args()

    # Resolve file list
    if args.files:
        file_paths = [Path(f) for f in args.files if not _is_am_locked(f)]
    elif args.all_files:
        file_paths = _collect_all_files()
    else:
        file_paths = _collect_changed_files()

    py_files = [str(p) for p in file_paths if p.suffix == ".py"]
    n_scanned = len(py_files)

    if n_scanned == 0:
        if not args.quiet:
            print("## Workspace SAST report\nScanned: 0 files\nFindings: 0\n(no Python files to scan)")
        return 0

    # Try anneal import path first
    anneal = _try_anneal_import()
    findings_raw: list[dict] = []
    used_path = "subprocess-fallback"

    if anneal is not None:
        CompositeSastRunner, RuffRunner, SemgrepRunner, SastFinding = anneal
        used_path = "anneal-import"
        try:
            runner = CompositeSastRunner([RuffRunner(), SemgrepRunner()])
            # anneal runners expect relative paths; compute relative to worktree
            rel_files = []
            for p in py_files:
                try:
                    rel_files.append(str(Path(p).relative_to(WORKSPACE_ROOT)))
                except ValueError:
                    rel_files.append(p)
            raw_findings = runner.run(WORKSPACE_ROOT, rel_files)
            findings_raw = [
                {
                    "severity": f.severity,
                    "file": f.file,
                    "line": f.line,
                    "rule_id": f.rule_id,
                    "message": f.message,
                    "tool": f.tool,
                }
                for f in raw_findings
            ]
        except Exception:
            # Fall through to subprocess fallback
            anneal = None
            used_path = "subprocess-fallback"

    if anneal is None:
        import shutil

        ruff_ok = bool(shutil.which("ruff"))
        semgrep_ok = bool(shutil.which("semgrep"))

        if not ruff_ok and not semgrep_ok:
            print(
                "## Workspace SAST report\n"
                "tool not installed: neither ruff nor semgrep found on PATH.\n"
                f"Scanned: {n_scanned} files\n"
                "Install: pip install ruff semgrep"
            )
            return 2

        findings_raw = _run_ruff_fallback(py_files) + _run_semgrep_fallback(py_files)

    report = _render_report(findings_raw, n_scanned, quiet=args.quiet)
    if report:
        print(report)
        # Also emit which runner path was used (stderr so it doesn't pollute markdown)
        print(f"[sast-runner: {used_path}]", file=sys.stderr)

    # Exit code
    has_critical = any(f["severity"] == "critical" for f in findings_raw)
    has_high = any(f["severity"] == "high" for f in findings_raw)
    return 1 if (has_critical or has_high) else 0


if __name__ == "__main__":
    sys.exit(main())
