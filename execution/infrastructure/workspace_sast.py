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
import ast
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
    # .claude/ is skipped EXCEPT .claude/skills/: skill scripts execute real work
    # (2026-08-27: gmaps-leads/extract_website_contacts.py pinned Haiku for months
    # because this rule never looked there).
    skip_dirs = _SKIP_DIRS_PY | {".anneal", "out", "dist", "build", "tests", "docs"}
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
        if ".claude" in path.parts and "skills" not in path.parts:
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
                            "(2026-06-14). Use claude-sonnet-5 minimum."
                        ),
                        "tool": "workspace-native",
                    }
                )
    return findings


def _rule_environ_copy() -> list[dict]:
    """Rule: never `copy.copy(os.environ)` (or copy.deepcopy) — use `dict(os.environ)`.

    `os.environ` is an `_Environ` proxy, not a dict. `copy.copy` returns another
    proxy that SHARES state with the live process env — mutations leak. See
    ~/.claude/rules/environ-not-copy-copy.md for the 2026-06-15 exhibit.
    """
    findings = []
    pat = re.compile(r"copy\.(?:copy|deepcopy)\(\s*os\.environ\s*\)")
    # Skip tests/ — test fixtures legitimately write files containing this exact pattern
    # to verify the SAST rule itself works. The runtime rule + this SAST guard the
    # actual production code; the test fixtures are documentation-by-example.
    skip_dirs = _SKIP_DIRS_PY | {"tests"}
    for py_path in WORKSPACE_ROOT.rglob("*.py"):
        if any(s in py_path.parts for s in skip_dirs):
            continue
        if _is_am_locked(str(py_path)):
            continue
        if py_path.resolve() == Path(__file__).resolve():
            continue
        try:
            lines = py_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = str(py_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        for lineno, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            # Skip comments and docstring-like lines mentioning the anti-pattern.
            if stripped.startswith("#"):
                continue
            if pat.search(line):
                findings.append(
                    {
                        "severity": "high",
                        "file": rel,
                        "line": lineno,
                        "rule_id": "environ-copy",
                        "message": (
                            "copy.copy(os.environ) shares state with the live process env. "
                            "Use dict(os.environ) for an independent snapshot. "
                            "See ~/.claude/rules/environ-not-copy-copy.md."
                        ),
                        "tool": "workspace-native",
                    }
                )
    return findings


def _rule_prior_art_pass_missing() -> list[dict]:
    """Rule: any directive that pairs with a source/scraper/enricher integration
    must include a '## Prior art pass' section per ~/.claude/rules/prior-art-first.md.

    Triggers: directive files at directives/**/*.md whose name matches
    *_source_*, *_scraper, *_api, *_gmail, *_rss, *_algolia, *_sheet*, OR whose
    paired execution script lives under sources/, scrapers/, enrichers/.

    Skip: subagent/ + AM-locked + files < 30 lines + names starting with _.
    """
    directives_root = WORKSPACE_ROOT / "directives"
    if not directives_root.exists():
        return []

    integration_name_hints = re.compile(
        r"(source|scraper|enricher|_api|_gmail|_rss|_algolia|_sheet|scrape|crawl)",
        re.IGNORECASE,
    )

    findings = []
    for md_path in directives_root.rglob("*.md"):
        try:
            md_path.relative_to(_SUBAGENT_DIR)
            continue
        except ValueError:
            pass
        if _is_am_locked(str(md_path)):
            continue
        if md_path.name.startswith("_"):
            continue

        if not integration_name_hints.search(md_path.name):
            try:
                content = md_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Also fire if the body explicitly references sources/ or scrapers/
            if not re.search(
                r"execution/.+/(sources|scrapers|enrichers)/|sources/.+\.py|scrapers/.+\.py",
                content,
            ):
                continue
        else:
            try:
                content = md_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

        if len(content.splitlines()) < 30:
            continue

        if not re.search(r"^## Prior art pass", content, re.MULTILINE):
            rel = str(md_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
            findings.append(
                {
                    "severity": "info",
                    "file": rel,
                    "line": 0,
                    "rule_id": "prior-art-pass-missing",
                    "message": (
                        "Directive integrates with an external service but is missing a "
                        "'## Prior art pass' section. Per ~/.claude/rules/prior-art-first.md, "
                        "every external-service integration directive must record the "
                        "10-min DevTools + GitHub prior-art pass output."
                    ),
                    "tool": "workspace-native",
                }
            )

    return findings


def _rule_personal_mode_with_pii() -> list[dict]:
    """Rule: `call_model(... mode='personal' ...)` MUST NOT appear in the same function
    body as PII-handling keywords.

    Defense-in-depth on top of the runtime `RuntimeError` raised by `call_model()` when
    sensitivity='sensitive' is passed. This SAST catches the silent case: a caller
    handling PII who forgets to pass sensitivity='sensitive' but enables personal-mode,
    which would leak data to GLM-5.2 (China-jurisdiction weights) via OpenRouter.

    Scope: .py files under execution/, directives/, tests/. Skips workspace_sast.py
    itself (this file documents the pattern), AM-locked paths, .anneal/.

    Severity: HIGH (sensitive data leak vector).

    Pattern: function body contains BOTH a `call_model(...)` invocation with `mode='personal'`
    AND any PII keyword: email, recipient, lead, candidate, cv, resume, cover_letter,
    phone, address, customer, pii.

    See: ~/.claude/rules/model-tier.md ("Client vs Personal mode" + Exhibit C).
    """
    import ast

    findings: list[dict] = []
    pii_re = re.compile(
        r"\b(email|recipient|lead|candidate|cv|resume|cover_letter|phone|address|customer|pii|personally_identifiable)\b",
        re.IGNORECASE,
    )
    # call_model(... mode="personal" ...) — string literal value, single or double quoted
    personal_mode_re = re.compile(
        r"\bcall_model\s*\([^)]*mode\s*=\s*['\"]personal['\"]",
        re.MULTILINE | re.DOTALL,
    )

    skip_dirs = _SKIP_DIRS | {".anneal", ".claude", "out", "dist", "build"}

    for path in WORKSPACE_ROOT.rglob("*.py"):
        if not path.is_file():
            continue
        if any(s in path.parts for s in skip_dirs):
            continue
        if _is_am_locked(str(path)):
            continue
        # Don't flag the SAST rule itself (contains the pattern as documentation).
        if path.resolve() == Path(__file__).resolve():
            continue
        # Don't flag the call_model implementation file (defines `mode='personal'` semantics).
        rel_str = str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/") if path.is_relative_to(WORKSPACE_ROOT) else ""
        if rel_str.endswith("execution/modules/model_router.py"):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "mode=" not in text or "call_model" not in text:
            continue

        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue

        # For each FunctionDef, AsyncFunctionDef: extract the source span and check.
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            try:
                func_src = ast.get_source_segment(text, node) or ""
            except Exception:
                continue
            if not personal_mode_re.search(func_src):
                continue
            pii_match = pii_re.search(func_src)
            if not pii_match:
                continue
            findings.append(
                {
                    "severity": "high",
                    "file": rel_str,
                    "line": node.lineno,
                    "rule_id": "personal-mode-with-pii",
                    "message": (
                        f"Function '{node.name}' uses call_model(mode='personal') and references "
                        f"PII keyword '{pii_match.group(0)}'. Personal-mode routes through GLM (Z.AI, "
                        f"public-only) — sensitive payloads MUST pass sensitivity='sensitive' to "
                        f"trigger the runtime guardrail, OR use mode='client'. "
                        f"See ~/.claude/rules/model-tier.md Exhibit C + Client/Personal mode section."
                    ),
                    "tool": "workspace-native",
                }
            )
    return findings


def _rule_ps1_non_ascii() -> list[dict]:
    """Rule: .ps1 files MUST be ASCII-only OR saved with UTF-8 BOM (EF BB BF).

    PowerShell 5.1 (default `powershell.exe` on Windows) reads BOM-less files as
    the system code page (cp1252). Multi-byte UTF-8 sequences (em dash, smart
    quotes, ellipsis, accented chars) get misinterpreted, breaking string parsing
    several lines downstream with misleading errors like "missing string terminator".

    See: ~/.claude/rules/powershell-ascii-only.md (2026-06-22 Exhibit A).

    Severity: MEDIUM (silent runtime failure on Windows PowerShell 5.1).
    """
    findings: list[dict] = []
    skip_dirs = _SKIP_DIRS | {".anneal", "out", "dist", "build", "node_modules"}
    UTF8_BOM = b"\xef\xbb\xbf"

    for path in WORKSPACE_ROOT.rglob("*.ps1"):
        if not path.is_file():
            continue
        if any(s in path.parts for s in skip_dirs):
            continue
        if _is_am_locked(str(path)):
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if raw.startswith(UTF8_BOM):
            continue  # BOM-flagged file — explicit opt-in to Unicode
        # Find first non-ASCII byte
        bad_idx = None
        for i, b in enumerate(raw):
            if b > 0x7F:
                bad_idx = i
                break
        if bad_idx is None:
            continue
        # Find line number
        lineno = raw[:bad_idx].count(b"\n") + 1
        # Decode the problem char for the message
        try:
            char = raw[bad_idx:bad_idx + 4].decode("utf-8", errors="replace")[:1]
        except Exception:
            char = "?"
        rel = str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/") if path.is_relative_to(WORKSPACE_ROOT) else str(path)
        findings.append(
            {
                "severity": "medium",
                "file": rel,
                "line": lineno,
                "rule_id": "ps1-non-ascii",
                "message": (
                    f".ps1 contains non-ASCII byte 0x{raw[bad_idx]:02x} (char {char!r}) at line {lineno}. "
                    f"PowerShell 5.1 will misread as cp1252 and break parsing downstream. "
                    f"Replace with ASCII OR save with UTF-8 BOM. See ~/.claude/rules/powershell-ascii-only.md."
                ),
                "tool": "workspace-native",
            }
        )
    return findings


# ── Known native rules ────────────────────────────────────────────────────────

# Projects that produce a user-facing artifact (sheet / digest / CV / lead
# list / rendered doc) and therefore owe an output-acceptance gate per
# ~/.claude/rules/output-acceptance-gate.md.
#
# 2026-08-04 rewrite: was hardcoded to 5 projects and only scanned workspace-
# root tests/. Now enumerates dynamically from directives/ + execution/ trees
# and scans BOTH workspace-root tests/ and execution/**/tests/ (project-local
# test dirs). Explicit skip-list still supported for docs-only or library-only
# directives that don't produce a user artifact.
_ACCEPTANCE_GATE_SKIP: frozenset[str] = frozenset({
    # Internal-only or infrastructure directives — no user-facing artifact.
    "add_webhook", "canary_monitoring", "glm_5_2_integration",
    "free_cc_proxy", "model_chooser", "portfolio_site",
    "self_outbound_system",  # workflow, tracked via HANDOFF phases
    # Bootstrapping / meta / template directives
    "prodcraft_autopilot", "prodcraft_shorts_pipeline",
    "prodcraft_video_edit_pipeline", "video_edit_client_pipeline",
    "client_call_followup", "likeness_release_template",
})

# Directive categories that plausibly produce a user-facing artifact and
# therefore owe an output-acceptance gate. Everything else (lead_sourcing/
# enrichment/personalization/custom_scrapers/infrastructure/subagent/
# n8n_workflows/crm_and_pm/google/rag/mobile_apps/) is either a library-
# style integration, plumbing, or internal tooling and is intentionally
# excluded — the acceptance-gate discipline is about the OUTPUT a human
# reads, not every integration.
_ACCEPTANCE_GATE_CATEGORIES: frozenset[str] = frozenset({
    "personal_workflows",
    "gtm_client_workflows",
    "content",
    "image_generation",
    "video",
})


def _acceptance_gate_project_slugs() -> list[str]:
    """Enumerate every project slug that should own an output-acceptance gate.

    Restricted to _ACCEPTANCE_GATE_CATEGORIES to avoid firing on every
    lead-source integration or scraper.
    """
    directives_root = WORKSPACE_ROOT / "directives"
    slugs: set[str] = set()

    if directives_root.exists():
        for md in directives_root.rglob("*.md"):
            if md.name.startswith("_"):
                continue
            rel_parts = md.relative_to(directives_root).parts
            if not rel_parts or rel_parts[0] not in _ACCEPTANCE_GATE_CATEGORIES:
                continue
            if _is_am_locked(str(md)):
                continue
            stem = md.stem
            if stem in _ACCEPTANCE_GATE_SKIP:
                continue
            slugs.add(stem)

    return sorted(slugs)


def _rule_acceptance_gate_missing() -> list[dict]:
    """Rule: every artifact-producing project must have a hard-failing,
    unskippable output-acceptance test under tests/ or execution/**/tests/
    (per ~/.claude/rules/output-acceptance-gate.md).

    2026-08-04 rewrite: dynamic project enumeration, dual test-root scan.

    Presence check only — it does not verify the gate is wired to fail the
    run or has a frozen corpus (human review item). info-severity (advisory).
    """
    workspace_tests = WORKSPACE_ROOT / "tests"
    findings: list[dict] = []

    # Collect all candidate test dirs: workspace-root tests/ AND
    # every execution/**/tests/ directory.
    test_roots: list[Path] = []
    if workspace_tests.exists():
        test_roots.append(workspace_tests)
    exec_root = WORKSPACE_ROOT / "execution"
    if exec_root.exists():
        for t in exec_root.rglob("tests"):
            if t.is_dir():
                parts_lower = {p.lower() for p in t.parts}
                if parts_lower & _SKIP_DIRS:
                    continue
                if _is_am_locked(str(t)):
                    continue
                test_roots.append(t)

    for slug in _acceptance_gate_project_slugs():
        patterns = (
            f"acceptance_{slug}.*",
            f"acceptance*{slug}*.*",
            f"*{slug}*acceptance*.*",
        )
        found = False
        for root in test_roots:
            for pat in patterns:
                if any(root.glob(pat)):
                    found = True
                    break
            if found:
                break
        if not found:
            findings.append(
                {
                    "severity": "info",
                    "file": f"tests/ (project: {slug})",
                    "line": 0,
                    "rule_id": "acceptance-gate-missing",
                    "message": (
                        f"Artifact-producing project '{slug}' has no output-acceptance "
                        f"gate (expected tests/acceptance_{slug}.* or equivalent). Per "
                        f"~/.claude/rules/output-acceptance-gate.md, every user-facing "
                        f"artifact needs an unskippable, hard-failing, corpus-backed gate "
                        f"that asserts on the OUTPUT (not mechanics). See "
                        f"tests/acceptance_job_search_v2.py for the reference shape. "
                        f"If '{slug}' does not produce a user-facing artifact, add its "
                        f"slug to _ACCEPTANCE_GATE_SKIP in workspace_sast.py."
                    ),
                    "tool": "workspace-native",
                }
            )
    return findings


def _rule_agent_md_frontmatter_haiku() -> list[dict]:
    """Rule: .claude/agents/*.md frontmatter MUST NOT use `model: haiku*`.

    Extends `haiku-banned` (which scans source/config) to catch Haiku creep
    in agent definitions. Per ~/.claude/rules/model-tier.md (2026-06-14),
    Haiku 4.5 is banned workspace-wide including sub-agents. Default is
    Sonnet 4.6.

    high-severity — an agent silently promoted to Haiku violates policy
    every time it fires.
    """
    findings: list[dict] = []
    agents_dir = WORKSPACE_ROOT / ".claude" / "agents"
    if not agents_dir.is_dir():
        return findings

    # Frontmatter is a YAML block bounded by ---. We only look at the first
    # such block. Line-oriented scan to keep the frontmatter parser tiny.
    haiku_re = re.compile(r"^\s*model\s*:\s*[\"']?(haiku[\w.\-]*|claude[-.]haiku[-.\w]*|anthropic/claude[-.]haiku[-.\w]*)",
                          re.IGNORECASE)

    for path in agents_dir.rglob("*.md"):
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        if not lines or lines[0].strip() != "---":
            continue
        # Frontmatter body = lines up to the next ---
        fm_lines: list[str] = []
        for i, ln in enumerate(lines[1:], start=2):
            if ln.strip() == "---":
                break
            fm_lines.append((i, ln))  # type: ignore[arg-type]
        for lineno, ln in fm_lines:  # type: ignore[assignment]
            if haiku_re.match(ln):
                rel = str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
                findings.append(
                    {
                        "severity": "high",
                        "file": rel,
                        "line": lineno,
                        "rule_id": "agent-md-frontmatter-haiku",
                        "message": (
                            "Agent frontmatter declares `model: haiku*`. Haiku 4.5 "
                            "is banned workspace-wide per ~/.claude/rules/model-tier.md. "
                            "Change to `model: sonnet` (default) or remove the line."
                        ),
                        "tool": "workspace-native",
                    }
                )
                break  # one finding per file is enough
    return findings


# Directories that indicate a deployed project (Cloudflare Workers/Pages,
# Vercel, etc.). If a project has any of these, it needs a live front-door
# synthetic per ~/.claude/rules/front-door-synthetic.md.
_DEPLOYED_PROJECT_SIGNALS: tuple[str, ...] = (
    "wrangler.toml", "wrangler.jsonc", "wrangler.json",
    "vercel.json", "netlify.toml",
)

# Skip these project dirs — they are template-only, infrastructure-only,
# or have documented no-front-door-by-design reasons.
_FRONT_DOOR_SKIP_DIRS: frozenset[str] = frozenset({
    "api-proxy",  # AM-locked
    "workspace_heartbeat",  # infrastructure health check, no user surface
    "web_app_astro_cf",  # template scaffold
    "job_search_cron",  # cron trigger only, no user URL
})


def _rule_front_door_missing() -> list[dict]:
    """Rule: every project with a deployed-artifact signal (wrangler.toml,
    vercel.json, etc.) MUST have a `tests/front_door_*` script that hits a
    live URL (SITE_URL / API_URL / equivalent), per
    ~/.claude/rules/front-door-synthetic.md.

    Fixture-only scripts do NOT count — the script body must reference a
    URL variable, curl call, requests.get, or fetch to be treated as a
    live check. (Enforces the 2026-06-18 Exhibit B tightening from
    front-door-synthetic.md: "no fixture-only synthetic counts as green.")

    Skips: AM-locked, template scaffolds, infrastructure-only projects
    without a user surface (see _FRONT_DOOR_SKIP_DIRS).

    high-severity — a deployed project without a live front-door check is
    the exact class of bug that lets stale-fallback ship for weeks.
    """
    findings: list[dict] = []
    exec_root = WORKSPACE_ROOT / "execution"
    if not exec_root.exists():
        return findings

    # Find every project dir containing a deployed-artifact signal.
    seen: set[Path] = set()
    for signal in _DEPLOYED_PROJECT_SIGNALS:
        for signal_path in exec_root.rglob(signal):
            proj_dir = signal_path.parent
            if proj_dir in seen:
                continue
            seen.add(proj_dir)

    # URL-fetch fingerprints that satisfy the "hits live URL" requirement.
    url_re = re.compile(
        r"(SITE_URL|API_URL|BASE_URL|LIVE_URL|PROD_URL|"
        r"\bcurl\s+[-a-zA-Z]*\s*\"?https?://|"
        r"requests\.(get|post|put|head)|"
        r"fetch\s*\(\s*[\"']https?://|"
        r"httpx\.(get|post|Client|AsyncClient))",
        re.IGNORECASE,
    )

    for proj_dir in sorted(seen):
        if _is_am_locked(str(proj_dir)):
            continue
        parts_lower = {p.lower() for p in proj_dir.parts}
        if parts_lower & _SKIP_DIRS:
            continue
        if proj_dir.name in _FRONT_DOOR_SKIP_DIRS:
            continue

        # Look for tests/front_door_*.* in the project dir, its parent dir
        # (many CF-Worker projects nest under a parent that owns tests/),
        # OR the workspace root's tests/ dir.
        candidates: list[Path] = []
        for search_dir in (proj_dir, proj_dir.parent):
            search_tests = search_dir / "tests"
            if search_tests.is_dir():
                candidates.extend(search_tests.glob("front_door_*"))
        workspace_tests = WORKSPACE_ROOT / "tests"
        if workspace_tests.is_dir():
            # Match on project dir name AND parent dir name (worker subdirs).
            candidates.extend(workspace_tests.glob(f"front_door_{proj_dir.name}*"))
            candidates.extend(workspace_tests.glob(f"front_door_{proj_dir.parent.name}*"))

        if not candidates:
            rel = str(proj_dir.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
            findings.append(
                {
                    "severity": "high",
                    "file": rel,
                    "line": 0,
                    "rule_id": "front-door-missing",
                    "message": (
                        f"Deployed project '{proj_dir.name}' has no "
                        f"tests/front_door_* script. Per "
                        f"~/.claude/rules/front-door-synthetic.md, every project "
                        f"with a user surface needs a synthetic that runs the "
                        f"actual user flow end-to-end against LIVE infra. If this "
                        f"project genuinely has no user surface, add its dir "
                        f"name to _FRONT_DOOR_SKIP_DIRS in workspace_sast.py."
                    ),
                    "tool": "workspace-native",
                }
            )
            continue

        # Verify at least one candidate reads a live URL.
        live = False
        for cand in candidates:
            try:
                text = cand.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if url_re.search(text):
                live = True
                break

        if not live:
            rel = str(candidates[0].relative_to(WORKSPACE_ROOT)).replace("\\", "/")
            findings.append(
                {
                    "severity": "high",
                    "file": rel,
                    "line": 0,
                    "rule_id": "front-door-fixture-only",
                    "message": (
                        f"Front-door script '{rel}' does not reference a live URL "
                        f"(no SITE_URL / curl / requests / fetch pattern found). "
                        f"Per the 2026-06-18 tightening of "
                        f"~/.claude/rules/front-door-synthetic.md, fixture-only "
                        f"scripts do NOT count as green. Either add a live-URL "
                        f"probe or rename to tests/parser_*."
                    ),
                    "tool": "workspace-native",
                }
            )

    return findings


# Regex families for the shipped-claim scanner.
_SHIPPED_CLAIM_RE = re.compile(
    r"\b(shipped|live|ready|deployed|probationary|100%\s+complete|"
    r"good\s+to\s+go|wrapped|all\s+set)\b",
    re.IGNORECASE,
)


def _rule_shipped_claim_stale() -> list[dict]:
    """Rule: HANDOFF*.md files claiming shipped/live/ready/deployed status
    for a specific project must show recent activity on that project's
    tree (git log --since=7.days). If the last commit touching the project
    tree is older than 7 days, the claim is likely stale — surface it.

    Warn severity (heuristic, may false-positive on genuinely-stable
    finished projects). Advisory, not blocking.

    Rationale: the 2026-08-04 workspace audit found job_search_v2 memory
    saying "LIVE-PROBATIONARY day 0/5" while the last cron run was 34
    days ago; anthropic_watch ledger 52 days stale but claimed shipped;
    prodcraft_autopilot queue frozen 43 days but "Phase 1 SHIPPED" in
    memory. The pattern: shipped-claim survives silence.

    Heuristic: walk each HANDOFF.md, extract each project slug it names
    (the containing directory or explicit `## <slug>` heading), check
    git log for changes to that dir in the last 7 days.
    """
    findings: list[dict] = []

    # Collect HANDOFF*.md files (workspace root + per-project). Skip
    # AM-locked and .anneal snapshots.
    handoff_paths: list[Path] = []
    for candidate in WORKSPACE_ROOT.rglob("HANDOFF*.md"):
        parts_lower = {p.lower() for p in candidate.parts}
        if parts_lower & (_SKIP_DIRS | {".anneal"}):
            continue
        if _is_am_locked(str(candidate)):
            continue
        handoff_paths.append(candidate)

    for hf in handoff_paths:
        try:
            text = hf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _SHIPPED_CLAIM_RE.search(text):
            continue

        # Determine the "project tree" to freshness-check. If HANDOFF is
        # at workspace root, we cannot narrow it — skip (root HANDOFF is
        # usually AM-related and lockdown-skipped anyway; but if not,
        # the operator's own diligence covers it). Otherwise, use the
        # HANDOFF's parent dir as the project tree.
        try:
            rel_parent = hf.parent.relative_to(WORKSPACE_ROOT)
        except ValueError:
            continue
        if str(rel_parent) in ("", "."):
            continue  # workspace-root HANDOFF — too broad to freshness-check

        project_tree = str(rel_parent).replace("\\", "/")

        # Freshness probe: `git log --since=7.days --oneline -- <tree>`
        try:
            proc = subprocess.run(
                ["git", "log", "--since=7.days", "--oneline", "--", project_tree],
                cwd=str(WORKSPACE_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            # Git unavailable or slow — skip this file rather than false-fire.
            continue
        if proc.returncode != 0:
            continue

        if proc.stdout.strip():
            # Fresh activity — claim is plausibly current.
            continue

        # No commits touching this tree in the last 7 days. Look up the
        # last commit that DID touch it, to include the age in the msg.
        try:
            age_proc = subprocess.run(
                ["git", "log", "-1", "--format=%cr|%h", "--", project_tree],
                cwd=str(WORKSPACE_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
            age_line = age_proc.stdout.strip() or "(no git history)"
        except (OSError, subprocess.SubprocessError):
            age_line = "(git unavailable)"

        rel = str(hf.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        findings.append(
            {
                "severity": "warn",
                "file": rel,
                "line": 0,
                "rule_id": "shipped-claim-stale",
                "message": (
                    f"{rel} contains shipped/live/ready/deployed framing, but "
                    f"the project tree '{project_tree}' has NO commits in the "
                    f"last 7 days (last touched: {age_line}). Either the claim "
                    f"is stale (update the HANDOFF), the project is genuinely "
                    f"stable-and-untouched (add a `## Freshness` note), or "
                    f"activity happens outside git (external cron writes to KV "
                    f"— add the cron's last-run URL to a `## Health probe` "
                    f"section that the auditor can hit). Per "
                    f"~/.claude/rules/front-door-synthetic.md + Pattern B in "
                    f"HARDENING_BACKLOG_WORKSPACE_2026-08-04.md."
                ),
                "tool": "workspace-native",
            }
        )

    return findings


def _rule_audit_stack_framing_without_evidence() -> list[dict]:
    """Rule (2026-07-01): the last 5 commit messages on the current branch
    that use 'done / shipped / ready / wrapped / 100% / good to go / clean
    forever' framing MUST reference at least 2 of the 6 mandatory audit-stack
    tools (per ~/.claude/rules/mandatory-audit-stack.md).

    Advisory (warn severity). The rule's own text acknowledges enforcement is
    prototype-level; this is the first mechanical layer.

    Audit-stack tools whose names satisfy the reference: 'front-door',
    'customer-pov' / 'acceptance', 'anneal', 'panel-pass' / 'lens', 'test suite'
    / 'pytest', 'pipeline-auditor' / 'adversarial'.
    """
    findings: list[dict] = []
    forbidden = re.compile(
        r"\b(done|shipped|ready|wrapped|100%|good to go|all set|clean forever|verified)\b",
        re.IGNORECASE,
    )
    audit_refs = re.compile(
        r"\b(front[-\s]?door|customer[-\s]?pov|acceptance|anneal|panel[-\s]?pass|"
        r"lens|pytest|test suite|pipeline[-\s]?auditor|adversarial|code[-\s]?reviewer)\b",
        re.IGNORECASE,
    )

    try:
        proc = subprocess.run(
            ["git", "log", "-5", "--format=%H%n%B%n---END---"],
            cwd=str(WORKSPACE_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return findings
    if proc.returncode != 0:
        return findings

    commits = [c.strip() for c in proc.stdout.split("---END---") if c.strip()]
    for commit in commits:
        lines = commit.splitlines()
        if not lines:
            continue
        sha = lines[0][:8]
        body = "\n".join(lines[1:])
        if not forbidden.search(body):
            continue
        # Framing found — require at least 2 audit refs.
        matches = audit_refs.findall(body)
        if len(set(m.lower() for m in matches)) < 2:
            findings.append(
                {
                    "severity": "warn",
                    "file": f"git commit {sha}",
                    "line": 0,
                    "rule_id": "audit-stack-framing-without-evidence",
                    "message": (
                        f"Commit {sha} uses 'done/shipped/ready/wrapped/verified' "
                        f"framing but references < 2 of the 6 mandatory audit-stack "
                        f"tools. Per ~/.claude/rules/mandatory-audit-stack.md, "
                        f"'done' claims must be paired with evidence that at least "
                        f"the front-door synthetic + one adversarial audit fired."
                    ),
                    "tool": "workspace-native",
                }
            )
    return findings


def _rule_pages_functions_untracked() -> list[dict]:
    """Rule: every .ts / .js / .mjs / .tsx / .jsx file inside any project's
    `functions/` directory (Cloudflare Pages convention) MUST be tracked in
    git. Untracked Pages Functions do NOT ship on `wrangler pages deploy` —
    they only work in local dev.

    Born from the 2026-08-03 yoga_jitendra dashboard incident: two Pages
    Functions (functions/api/dashboard-data.ts + functions/wa-out.ts) were
    written by a prior session but never `git add`ed. Local build looked
    fine; production served the V0.01 static fallback for 13 days while
    the client complained. Full exhibit in
    ~/.claude/rules/live-artifact-acceptance.md.

    high-severity — this is a shipped-broken pattern, not a style issue.
    """
    findings: list[dict] = []

    # Find every functions/ directory under execution/, one per project tree.
    exec_root = WORKSPACE_ROOT / "execution"
    if not exec_root.exists():
        return findings

    # Ask git ONCE for all tracked files, then check membership per candidate.
    # Avoids O(n) subprocess spawns when a project has many functions/ files.
    try:
        proc = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            cwd=str(WORKSPACE_ROOT),
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        # No git binary available (CI containers without git). Skip rather
        # than fail — a different environment check should catch missing git.
        return findings
    if proc.returncode != 0:
        return findings
    tracked = {
        line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()
    }

    # Discover functions/ dirs across projects. Skip .venv / node_modules /
    # dist / .anneal (already in _SKIP_DIRS).
    functions_dirs: list[Path] = []
    for path in exec_root.rglob("functions"):
        if not path.is_dir():
            continue
        parts_lower = {p.lower() for p in path.parts}
        if parts_lower & _SKIP_DIRS:
            continue
        # AM-lockdown: never surface findings inside the frozen AM tree.
        if _is_am_locked(str(path)):
            continue
        functions_dirs.append(path)

    exts = {".ts", ".js", ".mjs", ".tsx", ".jsx"}
    for fdir in functions_dirs:
        for src in fdir.rglob("*"):
            if not src.is_file() or src.suffix not in exts:
                continue
            # Path relative to workspace root, forward-slash, matching git output.
            rel = str(src.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
            if rel in tracked:
                continue
            findings.append(
                {
                    "severity": "high",
                    "file": rel,
                    "line": 0,
                    "rule_id": "pages-functions-untracked",
                    "message": (
                        f"Pages Function file untracked in git. `wrangler pages deploy` "
                        f"only ships tracked files — this file exists locally but will "
                        f"NOT reach production. Fix: `git add {rel}` and commit before "
                        f"the next deploy. See ~/.claude/rules/live-artifact-acceptance.md "
                        f"(Exhibit A: 2026-08-03 yoga_jitendra dashboard)."
                    ),
                    "tool": "workspace-native",
                }
            )
    return findings


# Substring pre-filter for _rule_probe_failure_as_verdict. Must stay a superset
# of `negative_vocab` inside that rule, or the gate would skip a real finding.
_NEGATIVE_HINT = re.compile(
    r"dead|invalid|nxdomain|no_?mx|null_?mx|not_?found|bounced|"
    r"unreachable|nonexistent|does_?not_?exist|undeliverable|disposable",
    re.IGNORECASE,
)


def _rule_probe_failure_as_verdict() -> list[dict]:
    """Rule: a transport failure must never be coded as a negative finding.

    When a probe (DNS, HTTP, verification API) fails for reasons unrelated to
    the thing being probed, that failure needs its own ERROR_*/UNKNOWN verdict.
    Folding it into the negative verdict means a network outage looks like
    "every record is dead" -- and whatever consumes the verdict then deletes
    the population. See ~/.claude/rules/probe-failure-is-not-a-verdict.md
    (2026-08-26: blocked port 53 made all 186 domains in a lead list resolve
    as ERROR_TIMEOUT; had timeouts been coded NO_MX, 211 leads would have been
    deleted).

    high-severity -- this is a data-loss class, not a style issue.
    """
    findings = []

    # Exception names that mean "the probe did not complete", not "the answer is no".
    transport_exc = {
        "Timeout", "LifetimeTimeout", "ReadTimeout", "ConnectTimeout",
        "NoNameservers", "ConnectionError", "ConnectionRefusedError",
        "ConnectionResetError", "URLError", "TimeoutError", "socket.timeout",
        "SSLError", "ProxyError", "ChunkedEncodingError", "OSError", "IOError",
        "Exception", "BaseException", "DNSException",
    }
    # String values that read as an authoritative negative finding.
    # Deliberately narrow. Generic status words ("fail", "bad", "error") are
    # excluded -- a test harness printing "FAIL" from an except block is not this
    # bug. Only vocabulary that reads as an authoritative finding ABOUT THE
    # PROBED ENTITY, i.e. the kind a cleanup step would act on destructively.
    negative_vocab = re.compile(
        r"^(dead|invalid|nxdomain|no_?mx|null_?mx|not_?found|bounced|"
        r"unreachable|nonexistent|does_?not_?exist|undeliverable|disposable)$",
        re.IGNORECASE,
    )
    # Prefixes that correctly mark the value as "could not determine".
    safe_prefix = re.compile(r"^(error|unknown|skip|pending|retry|indeterminate|unresolved)",
                             re.IGNORECASE)

    def _exc_names(handler) -> set[str]:
        names = set()
        node = handler.type
        if node is None:
            names.add("Exception")  # bare except
            return names
        targets = node.elts if isinstance(node, ast.Tuple) else [node]
        for t in targets:
            if isinstance(t, ast.Name):
                names.add(t.id)
            elif isinstance(t, ast.Attribute):
                names.add(t.attr)
        return names

    def _string_constants(node) -> list[str]:
        out = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                out.append(sub.value)
        return out

    skip_dirs = _SKIP_DIRS_PY | {"tests"}
    for py_path in WORKSPACE_ROOT.rglob("*.py"):
        if any(skip in py_path.parts for skip in skip_dirs):
            continue
        if _is_am_locked(str(py_path)):
            continue
        if py_path.resolve() == Path(__file__).resolve():
            continue
        try:
            source = py_path.read_text(encoding="utf-8", errors="replace")
            # Cheap gate before the expensive parse: this rule can only fire on a
            # file that has an except handler AND a negative-verdict word in it.
            # Skips the AST cost on the large majority of files.
            if "except" not in source or not _NEGATIVE_HINT.search(source):
                continue
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            # Unreadable or not valid Python for this interpreter -- nothing to
            # assert about it. Skipped deliberately, not silently swallowed.
            continue
        rel = str(py_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if not (_exc_names(node) & transport_exc):
                continue
            for value in _string_constants(node):
                v = value.strip()
                if safe_prefix.match(v):
                    continue
                if negative_vocab.match(v):
                    findings.append(
                        {
                            "severity": "high",
                            "file": rel,
                            "line": node.lineno,
                            "rule_id": "probe-failure-as-verdict",
                            "message": (
                                f"except handler for a transport failure assigns the "
                                f"negative verdict {v!r}. A probe that could not complete "
                                f"is not an authoritative 'no' -- give it an ERROR_*/UNKNOWN "
                                f"verdict and exclude it from any deletion set. "
                                f"See ~/.claude/rules/probe-failure-is-not-a-verdict.md."
                            ),
                            "tool": "workspace-native",
                        }
                    )
                    break
    return findings


def _rule_py_launcher_shebang() -> list[dict]:
    """Rule: no bare `#!/usr/bin/env python` shebang on workspace scripts.

    The Windows `py` launcher dispatches on the shebang, so `py script.py` and
    `py -c` can select DIFFERENT interpreters with different site-packages.
    A package installed by `py -m pip` is then missing from the interpreter
    that actually runs the file, and the symptom reads as "pip lied".
    (2026-08-26: instantly_guard.py died on --help with ImportError for
    dnspython, which was installed and importable the whole time.)

    medium-severity -- breaks execution, but loudly rather than silently.
    """
    findings = []
    bare = re.compile(r"^#!.*[/ ]python(w)?(\.exe)?\s*$")
    for py_path in WORKSPACE_ROOT.rglob("*.py"):
        if any(skip in py_path.parts for skip in _SKIP_DIRS_PY):
            continue
        if _is_am_locked(str(py_path)):
            continue
        try:
            with py_path.open(encoding="utf-8", errors="replace") as fh:
                first = fh.readline()
        except OSError:
            continue
        if not first.startswith("#!"):
            continue
        if not bare.match(first.rstrip()):
            continue  # version-pinned shebang (python3.14 etc) is explicit -- fine
        rel = str(py_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        findings.append(
            {
                "severity": "medium",
                "file": rel,
                "line": 1,
                "rule_id": "py-launcher-shebang",
                "message": (
                    "bare `#!/usr/bin/env python` shebang: the Windows py launcher "
                    "dispatches on it, so `py this.py` may run a different interpreter "
                    "than `py -m pip` installs into. Remove the shebang, or invoke as "
                    "`py -3.14 <script>`. See .claude/rules/python-hardening.md #7."
                ),
                "tool": "workspace-native",
            }
        )
    return findings


def _rule_legacy_model_pin() -> list[dict]:
    """Rule: no 4.x Claude model pinned as a default in executing code.

    `claude-sonnet-4-6` / `claude-opus-4-[1-8]` / `claude-sonnet-4-5` are superseded
    by the 5-series, which is cheaper AND better ($2/$10 vs $3/$15 for Sonnet).
    The 2026-08-12 sweep moved the registry but missed ~15 hand-pinned defaults
    (`DEFAULT_MODEL = ...`, `MODEL = ...`, `"anthropic_model": ...`) that were
    found by hand on 2026-08-27. This catches the shape mechanically.

    Only DEFAULT-style assignments are flagged; pricing-table rows that keep a
    legacy model so old run records still cost-resolve are legitimate and do
    not match (they are dict keys, not `model = "..."` assignments).

    medium-severity -- wrong cost/quality, but not silent data loss.
    """
    findings = []
    pin_re = re.compile(
        r"""model[\w"']*\s*[:=]\s*["']claude-(?:sonnet-4-[56]|opus-4-[1-8]|haiku-3)[\w.-]*["']""",
        re.IGNORECASE,
    )
    suffixes = (".py", ".ts", ".js", ".jsx", ".tsx", ".json", ".toml", ".mjs")
    skip_dirs = _SKIP_DIRS_PY | {".anneal", "out", "dist", "build", "tests", "docs", "_archived"}
    # Tracked files only, via git: sub-second, and untracked code never ships.
    # A second full-tree rglob over OneDrive pushed --all past the pre-push
    # timeout (HARDENING_BACKLOG item 9 is the structural fix; this sidesteps it).
    try:
        ls = subprocess.run(
            ["git", "ls-files", "-z"], cwd=WORKSPACE_ROOT, capture_output=True,
            text=True, encoding="utf-8", errors="replace", check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return findings
    for rel_path in ls.split("\0"):
        if not rel_path:
            continue
        path = WORKSPACE_ROOT / rel_path
        if path.suffix not in suffixes:
            continue
        if any(s in path.parts for s in skip_dirs):
            continue
        if ".claude" in path.parts and "skills" not in path.parts:
            continue
        if "api-proxy" in path.parts or _is_am_locked(str(path)):
            continue
        if path.name == Path(__file__).name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "claude-" not in text:
            continue
        rel = str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not pin_re.search(line):
                continue
            if re.search(r"legacy|historical|kept so|back-?compat", line, re.IGNORECASE):
                continue
            findings.append(
                {
                    "severity": "medium",
                    "file": rel,
                    "line": lineno,
                    "rule_id": "legacy-model-pin",
                    "message": (
                        "A 4.x Claude model is pinned as a default. The 5-series is the "
                        "current tier map (claude-sonnet-5 execution / claude-fable-5 "
                        "judgement) per ~/.claude/rules/model-tier.md; 4.x rows belong "
                        "only in pricing tables for historical cost lookups."
                    ),
                    "tool": "workspace-native",
                }
            )
    return findings


_NATIVE_RULES: dict[str, callable] = {
    "exit-criteria-missing": _rule_exit_criteria_missing,
    "subprocess-encoding": _rule_subprocess_encoding,
    "haiku-banned": _rule_haiku_banned,
    "environ-copy": _rule_environ_copy,
    "prior-art-pass-missing": _rule_prior_art_pass_missing,
    "personal-mode-with-pii": _rule_personal_mode_with_pii,
    "ps1-non-ascii": _rule_ps1_non_ascii,
    "acceptance-gate-missing": _rule_acceptance_gate_missing,
    "audit-stack-framing-without-evidence": _rule_audit_stack_framing_without_evidence,
    "pages-functions-untracked": _rule_pages_functions_untracked,
    "agent-md-frontmatter-haiku": _rule_agent_md_frontmatter_haiku,
    "front-door-missing": _rule_front_door_missing,
    "shipped-claim-stale": _rule_shipped_claim_stale,
    "probe-failure-as-verdict": _rule_probe_failure_as_verdict,
    "py-launcher-shebang": _rule_py_launcher_shebang,
    "legacy-model-pin": _rule_legacy_model_pin,
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
