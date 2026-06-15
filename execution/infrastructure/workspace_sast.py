"""Workspace SAST pre-pass runner.

Runs ruff and semgrep over Python files in execution/ and surfaces findings
as a markdown report.  Designed to run as a Claude Code PostToolUse hook
(warn-mode) or manually before PRs.

Also includes two workspace-native rules that don't require external tools:
  - exit-criteria-missing : directives/**/*.md without an ## Exit Criteria heading
  - subprocess-encoding   : execution/**/*.py subprocess.run() missing encoding=

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
import re
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
# "warn" sits between low and info (advisory, non-blocking)
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "warn": 4, "info": 5}


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


# ── Workspace-native rules ───────────────────────────────────────────────────

# Directories to skip for subprocess-encoding scan
# .anneal/ is a throwaway audit-worktree created by the anneal tool — its files
# are snapshots of other repos, not authoritative workspace source, and should
# never be patched by workspace SAST.
_SKIP_DIRS_PY = {".venv", "__pycache__", ".tmp", "node_modules", ".git", ".anneal"}
# Subagent directives that legitimately skip Exit Criteria
_SUBAGENT_DIR = WORKSPACE_ROOT / "directives" / "subagent"


def _rule_exit_criteria_missing() -> list[dict]:
    """Rule: every directives/**/*.md must contain '## Exit Criteria'.

    Exceptions (not flagged):
    - directives/_TEMPLATE.md
    - directives/subagent/* (internal SOPs, no Exit Criteria required)
    - Files < 30 lines (stubs)
    - Files whose name starts with '_'
    """
    directives_root = WORKSPACE_ROOT / "directives"
    if not directives_root.exists():
        return []

    findings = []
    for md_path in directives_root.rglob("*.md"):
        # Skip subagent/ directory
        try:
            md_path.relative_to(_SUBAGENT_DIR)
            continue  # inside subagent/
        except ValueError:
            pass

        # Skip AM-locked directives (frozen project, no-touch per CLAUDE.local.md).
        # These files legitimately have no Exit Criteria and can never be edited.
        if _is_am_locked(str(md_path)):
            continue

        # Skip template-like files (name starts with _)
        if md_path.name.startswith("_"):
            continue

        # Read and check
        try:
            content = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = content.splitlines()
        if len(lines) < 30:
            continue  # stub

        if not re.search(r"^## Exit Criteria", content, re.MULTILINE):
            rel = str(md_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
            findings.append(
                {
                    "severity": "info",
                    "file": rel,
                    "line": 0,
                    "rule_id": "exit-criteria-missing",
                    "message": "Directive is missing an '## Exit Criteria' section.",
                    "tool": "workspace-native",
                }
            )

    return findings


# Regex to find subprocess.run( calls.  We look for the opening and then
# capture everything up to the matching close-paren.  A simple line-level
# grep is fast and catches the overwhelming majority of real-world usages
# (multi-line calls where text=True / capture_output=True appear on later
# lines are rare in this codebase).  The per-file approach reads each file
# once and checks line-by-line for the violation pattern.

_SUBPROC_OPEN = re.compile(r"\bsubprocess\.run\s*\(")
# kwargs that trigger the encoding requirement
_SUBPROC_TRIGGER = re.compile(r"\b(?:text\s*=\s*True|capture_output\s*=\s*True)\b")
_SUBPROC_ENCODING = re.compile(r"\bencoding\s*=")


def _rule_subprocess_encoding() -> list[dict]:
    """Rule: subprocess.run() with text=True or capture_output=True must include encoding=.

    Scans all .py files in the workspace except excluded dirs and AM-locked paths.
    Uses a sliding-window approach: once subprocess.run( is found, accumulate
    lines until the call closes (balanced parentheses), then check kwargs.
    """
    findings = []

    # Gather all .py files under the workspace root (not just execution/)
    for py_path in WORKSPACE_ROOT.rglob("*.py"):
        # Skip excluded dirs
        if any(skip in py_path.parts for skip in _SKIP_DIRS_PY):
            continue
        if _is_am_locked(str(py_path)):
            continue

        try:
            lines = py_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        i = 0
        while i < len(lines):
            line = lines[i]
            # Detect start of subprocess.run(
            if _SUBPROC_OPEN.search(line):
                # Accumulate the full call block (balance parens)
                call_lines = [line]
                start_lineno = i + 1  # 1-based
                depth = line.count("(") - line.count(")")
                j = i + 1
                while depth > 0 and j < len(lines):
                    call_lines.append(lines[j])
                    depth += lines[j].count("(") - lines[j].count(")")
                    j += 1

                call_text = "\n".join(call_lines)

                # Only flag if a trigger kwarg is present
                if _SUBPROC_TRIGGER.search(call_text):
                    # Check if encoding= is also present
                    if not _SUBPROC_ENCODING.search(call_text):
                        rel = str(py_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
                        findings.append(
                            {
                                "severity": "warn",
                                "file": rel,
                                "line": start_lineno,
                                "rule_id": "subprocess-encoding",
                                "message": (
                                    'subprocess.run() with text=True or capture_output=True '
                                    'is missing encoding="utf-8", errors="replace". '
                                    "Windows cp1252 default crashes on bytes >= 0x80."
                                ),
                                "tool": "workspace-native",
                            }
                        )
                i = j  # skip past the call block
            else:
                i += 1

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
    counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "warn": 0, "info": 0}
    for f in findings:
        sev = f["severity"]
        counts[sev] = counts.get(sev, 0) + 1

    total = sum(counts.values())
    scanned_label = str(n_scanned) if n_scanned else "(workspace-native)"
    header = (
        "## Workspace SAST report\n"
        f"Scanned: {scanned_label} files\n"
        f"Findings: {total} (critical: {counts['critical']}, high: {counts['high']}, "
        f"medium: {counts['medium']}, low: {counts['low']}, warn: {counts['warn']}, info: {counts['info']})\n"
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


def _rule_haiku_banned() -> list[dict]:
    """Rule: Claude Haiku 4.5 is banned workspace-wide per ~/.claude/rules/model-tier.md (2026-06-14).

    Flags any source/config reference to a Haiku 4.5 model id in actively-
    executing code. Skips:
      - AM-locked paths (frozen project)
      - api-proxy/ (explicit AM lockdown)
      - Docs (.md), workspace templates (_TEMPLATE*), and HARDENING_BACKLOG /
        HANDOFF / CLAUDE.md (these describe the ban, not invoke Haiku)
      - tests/ (may legitimately exercise Haiku-handling code paths)
      - lines that explicitly mark Haiku as banned/forbidden

    Scope: .py / .ts / .js / .json under execution/ (and equivalent).
    """
    findings = []
    haiku_re = re.compile(
        r"(?:anthropic[/.])?claude[-.]haiku[-.]4[-.]\d",
        re.IGNORECASE,
    )
    ban_marker_re = re.compile(
        r"haiku.*(?:banned|ban\b|forbidden|do[- ]?not[- ]?use|frozen|legacy|previous|earlier)",
        re.IGNORECASE,
    )
    # Only flag actively-executing source code; skip docs/notes/templates/tests.
    suffixes = (".py", ".ts", ".js", ".jsx", ".tsx", ".json", ".toml")
    skip_dirs = _SKIP_DIRS_PY | {".anneal", ".claude", "out", "dist", "build", "tests", "docs"}
    # Workspace-level docs that discuss the ban itself.
    skip_filenames = {"HANDOFF.md", "CLAUDE.md", "CLAUDE.local.md", "HARDENING_BACKLOG.md", "STATUS.md", "README.md"}
    # AM-coupled-by-purpose shared modules (not name-locked but functionally frozen
    # per the AM handoff). Listed by relative path so the operator can review and
    # remove later if they become non-AM.
    skip_relpaths = {
        "execution/modules/outputs/auto_reply.py",
        "execution/modules/reply_classifier.py",
    }

    for path in WORKSPACE_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in suffixes:
            continue
        if any(s in path.parts for s in skip_dirs):
            continue
        # Explicit AM lockdown (api-proxy/) beyond the name-pattern check.
        rel_parts = path.relative_to(WORKSPACE_ROOT).parts if path.is_relative_to(WORKSPACE_ROOT) else path.parts
        if "api-proxy" in rel_parts:
            continue
        if _is_am_locked(str(path)):
            continue
        if path.name in skip_filenames:
            continue
        # Templates show example tier maps but don't execute.
        if path.name.startswith("_TEMPLATE"):
            continue
        # AM-coupled-by-purpose modules listed above.
        rel_str = str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/") if path.is_relative_to(WORKSPACE_ROOT) else ""
        if rel_str in skip_relpaths:
            continue
        # Never flag the SAST rule itself (this file contains the pattern).
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not haiku_re.search(text):
            continue
        rel = str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        text_lines = text.splitlines()
        for lineno, line in enumerate(text_lines, start=1):
            if not haiku_re.search(line):
                continue
            # Skip if this line OR the previous 2 lines mark Haiku as banned.
            prev_window = "\n".join(text_lines[max(0, lineno - 3):lineno])
            if ban_marker_re.search(prev_window):
                continue
            if not ban_marker_re.search(line):
                findings.append(
                    {
                        "severity": "critical",
                        "file": rel,
                        "line": lineno,
                        "rule_id": "haiku-banned",
                        "message": (
                            "Claude Haiku 4.5 reference found. Haiku 4.5 is banned "
                            "workspace-wide per ~/.claude/rules/model-tier.md "
                            "(2026-06-14). Use Sonnet 4.6 minimum."
                        ),
                        "tool": "workspace-native",
                    }
                )
    return findings


# ── Known native rules ────────────────────────────────────────────────────────

_NATIVE_RULES: dict[str, callable] = {
    "exit-criteria-missing": _rule_exit_criteria_missing,
    "subprocess-encoding": _rule_subprocess_encoding,
    "haiku-banned": _rule_haiku_banned,
}

_ALL_NATIVE_RULE_NAMES = list(_NATIVE_RULES.keys())


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Workspace SAST pre-pass (ruff + semgrep + native rules)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--changed", action="store_true", default=True,
                      help="Scan changed .py files in execution/ vs HEAD (default)")
    mode.add_argument("--all", dest="all_files", action="store_true",
                      help="Scan all execution/**/*.py")
    mode.add_argument("--files", nargs="+", metavar="FILE",
                      help="Scan explicit file paths")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress output when there are no findings")
    parser.add_argument(
        "--rules",
        metavar="RULE[,RULE...]",
        default=None,
        help=(
            "Comma-separated list of workspace-native rules to run in isolation "
            "(skips ruff/semgrep). Available: "
            + ", ".join(_ALL_NATIVE_RULE_NAMES)
        ),
    )
    args = parser.parse_args()

    # ── Native-rules-only mode ────────────────────────────────────────────────
    if args.rules is not None:
        requested = [r.strip() for r in args.rules.split(",") if r.strip()]
        unknown = [r for r in requested if r not in _NATIVE_RULES]
        if unknown:
            print(f"Unknown rule(s): {', '.join(unknown)}", file=sys.stderr)
            print(f"Available: {', '.join(_ALL_NATIVE_RULE_NAMES)}", file=sys.stderr)
            return 1

        native_findings: list[dict] = []
        for rule_name in requested:
            native_findings.extend(_NATIVE_RULES[rule_name]())

        # "warn" severity is informational for the report but not high/critical
        n_scanned_native = 0  # we scan directives/py files independently
        report = _render_report(native_findings, n_scanned_native, quiet=args.quiet)
        if report:
            print(report)
        elif not args.quiet:
            print(f"## Workspace SAST report\nScanned: (workspace-native)\nFindings: 0\n(no issues found for rules: {', '.join(requested)})")
        return 0  # native rules are advisory — never block

    # ── Resolve Python file list for ruff/semgrep ─────────────────────────────
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

    # ── Always append workspace-native rule findings ──────────────────────────
    for rule_fn in _NATIVE_RULES.values():
        findings_raw.extend(rule_fn())

    report = _render_report(findings_raw, n_scanned, quiet=args.quiet)
    if report:
        print(report)
        # Also emit which runner path was used (stderr so it doesn't pollute markdown)
        print(f"[sast-runner: {used_path}]", file=sys.stderr)

    # Exit code: native rules are advisory (info/warn) — don't affect exit code
    has_critical = any(f["severity"] == "critical" for f in findings_raw)
    has_high = any(f["severity"] == "high" for f in findings_raw)
    return 1 if (has_critical or has_high) else 0


if __name__ == "__main__":
    sys.exit(main())
