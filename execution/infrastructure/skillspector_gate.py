"""SkillSpector install gate — the ONE blocking gate of the plugin advisor (PreToolUse on Bash).

description: PreToolUse hook. Detects a bash command that is about to install/clone an UNVETTED
             skill or plugin (git clone into/near .claude/skills, cp/mv into .claude/skills or
             .claude/plugins, `agent-reach add`, plugin enable). When detected AND a local target
             is scannable, runs `skillspector scan <target> --no-llm -f json`; on max severity
             HIGH/CRITICAL it BLOCKS and asks the operator (surfacing the finding). Anything below
             HIGH is allowed with a one-line note. Tightly scoped so ordinary bash never trips it.
             Fail-open: skillspector missing, timeout, or any error -> allow untouched, never blocks.
inputs: stdin PreToolUse hook JSON {tool_name, tool_input:{command}, session_id}; CLI:
        `python3 execution/infrastructure/skillspector_gate.py check "<bash command>"`.
outputs: PreToolUse hook JSON on stdout when it asks (permissionDecision=ask); a one-line note on
         stderr for the allow-with-note case; nothing when the command is not an install.
         Exit 0 always (fail-open — the gate never aborts the session).

See also: directives/infrastructure/claude_plugins.md, directives/infrastructure/jev.md
"""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Severity ladder (skillspector risk_assessment.max_issue_severity).
_SEVERITY_ORDER = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
BLOCK_SEVERITIES = {"HIGH", "CRITICAL"}
SCAN_TIMEOUT_S = 90.0

# A skill/plugin install destination.
_SKILL_DIR_RE = re.compile(r"\.claude/(?:skills|plugins)\b")
# A repo/url that is itself skill- or plugin-shaped.
_SKILLISH_RE = re.compile(r"skill|plugin", re.IGNORECASE)


# ---------------------------------------------------------------------------------------
# detection (pure)
# ---------------------------------------------------------------------------------------

def _tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def detect(command: str) -> dict[str, Any] | None:
    """Return {kind, target, scannable} if the command installs a skill/plugin, else None.

    Tightly scoped: fires only on git clone / cp / mv that touch .claude/skills|plugins (or a
    skill-ish repo), `agent-reach add`, or a plugin enable. `target` is a LOCAL path (scannable)
    for cp/mv, a URL for git clone, or None (not scannable) for agent-reach/plugin enable.
    """
    if not command or not command.strip():
        return None
    toks = _tokens(command)
    if not toks:
        return None
    lower = command.lower()

    # agent-reach add <channel>
    if re.search(r"\bagent-reach\s+add\b", lower):
        return {"kind": "agent-reach", "target": None, "scannable": False}

    # plugin enable (claude plugin ... enable / --enable-plugin)
    if re.search(r"\bplugin\b.*\benable\b", lower) or "--enable-plugin" in lower:
        return {"kind": "plugin", "target": None, "scannable": False}

    # git clone <url> [dest]
    if re.search(r"\bgit\s+clone\b", lower):
        rest = [t for t in toks[toks.index("clone") + 1:] if not t.startswith("-")] \
            if "clone" in toks else []
        url = rest[0] if rest else ""
        dest = rest[1] if len(rest) > 1 else ""
        into_skills = bool(_SKILL_DIR_RE.search(dest) or _SKILL_DIR_RE.search(command))
        skillish = bool(_SKILLISH_RE.search(url))
        if into_skills or skillish:
            # Dir does not exist yet (pre-clone), so scan the remote URL (needs network; fail-open).
            return {"kind": "clone", "target": url or None, "scannable": bool(url)}
        return None

    # cp / mv into .claude/skills|plugins — source already exists locally, so it is scannable.
    if toks[0] in ("cp", "mv"):
        if not _SKILL_DIR_RE.search(command):
            return None
        args = [t for t in toks[1:] if not t.startswith("-")]
        if len(args) < 2:
            return None
        dest = args[-1]
        if not _SKILL_DIR_RE.search(dest):
            return None  # only guard when the DESTINATION is a skills/plugins dir
        for src in args[:-1]:
            return {"kind": "copy", "target": src, "scannable": True}
    return None


# ---------------------------------------------------------------------------------------
# scanning
# ---------------------------------------------------------------------------------------

def _scan_path(target: str) -> str:
    """Resolve the cp/mv source to the directory skillspector should scan (the SKILL.md dir)."""
    p = (PROJECT_ROOT / target).resolve() if not Path(target).is_absolute() else Path(target).resolve()
    if p.is_dir():
        return str(p)
    # A file (e.g. SKILL.md or a single script) -> scan its parent skill dir.
    return str(p.parent)


def scan(target: str, *, timeout_s: float = SCAN_TIMEOUT_S) -> dict[str, Any]:
    """Run `skillspector scan <target> --no-llm -f json`. Fail-open dict on any problem.

    Returns {max_severity, score, issue_count, error}. `error` set (and max_severity NONE) means
    'could not scan' — the caller must treat that as allow-with-note, never as a block.
    """
    exe = shutil.which("skillspector")
    if not exe:
        return {"max_severity": "NONE", "score": 0, "issue_count": 0, "error": "skillspector not installed"}
    scan_arg = _scan_path(target) if "://" not in target and not target.startswith("git@") else target
    try:
        proc = subprocess.run(
            [exe, "scan", scan_arg, "--no-llm", "-f", "json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout_s, cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"max_severity": "NONE", "score": 0, "issue_count": 0, "error": f"scan timed out after {timeout_s}s"}
    except (OSError, ValueError) as exc:
        return {"max_severity": "NONE", "score": 0, "issue_count": 0, "error": f"scan failed: {exc}"}
    try:
        data = json.loads(proc.stdout or "{}")
    except ValueError:
        return {"max_severity": "NONE", "score": 0, "issue_count": 0,
                "error": f"scan returned non-JSON (exit {proc.returncode})"}
    ra = data.get("risk_assessment") or {}
    sev = str(ra.get("max_issue_severity") or ra.get("severity") or "NONE").upper()
    if sev not in _SEVERITY_ORDER:
        sev = "NONE"
    return {"max_severity": sev, "score": int(ra.get("score") or 0),
            "issue_count": len(data.get("issues") or []), "error": None}


# ---------------------------------------------------------------------------------------
# evaluation (pure given a scan fn) + hook entry
# ---------------------------------------------------------------------------------------

def evaluate(command: str, *, scan_fn: Callable[[str], dict[str, Any]] | None = None) -> dict[str, Any]:
    """Decide what to do with a bash command.

    action: 'pass'  -> not an install; stay silent.
            'note'  -> install detected but not blockable (below HIGH, unscannable, or scan failed).
            'ask'   -> HIGH/CRITICAL finding; block and ask the operator.
    """
    det = detect(command)
    if det is None:
        return {"action": "pass", "detect": None}
    if not det["scannable"] or not det.get("target"):
        return {"action": "note", "detect": det, "scan": None,
                "message": f"skillspector-gate: about to {det['kind']} a skill/plugin — "
                           "skillspector can't auto-scan this; review the source before trusting it."}
    scanner = scan_fn or scan
    result = scanner(det["target"])
    sev = str(result.get("max_severity", "NONE")).upper()
    if result.get("error"):
        return {"action": "note", "detect": det, "scan": result,
                "message": f"skillspector-gate: could not scan {det['target']} "
                           f"({result['error']}) — review it manually before trusting it."}
    if sev in BLOCK_SEVERITIES:
        return {"action": "ask", "detect": det, "scan": result,
                "message": f"skillspector-gate: BLOCKED — {det['target']} scans {sev} "
                           f"(risk score {result.get('score')}, {result.get('issue_count')} issue(s)). "
                           "This is an unvetted skill/plugin install. Approve only if you trust the source."}
    return {"action": "note", "detect": det, "scan": result,
            "message": f"skillspector-gate: {det['target']} scans {sev} (clean enough) — allowed."}


def run_hook(stdin_text: str) -> int:
    """PreToolUse entry. Prints ask-JSON on a block, a note on stderr otherwise, exit 0 always."""
    try:
        payload = json.loads(stdin_text or "{}")
    except ValueError:
        return 0
    if payload.get("tool_name") not in (None, "Bash"):
        return 0
    command = str((payload.get("tool_input") or {}).get("command") or "")
    if not command:
        return 0
    verdict = evaluate(command)
    action = verdict["action"]
    if action == "pass":
        return 0
    if action == "ask":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": verdict["message"],
        }}))
        return 0
    # note: non-blocking, surfaced in the transcript via stderr
    print(verdict["message"], file=sys.stderr)
    return 0


def main(argv: list[str]) -> int:
    cmd = (argv[0] if argv else "hook").lower()
    if cmd == "hook":
        return run_hook(sys.stdin.read())
    if cmd == "check":
        print(json.dumps(evaluate(" ".join(argv[1:])), indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # a PreToolUse hook must never abort the session (fail-open)
        if (sys.argv[1:2] or [""])[0] in ("", "hook"):
            print(f"skillspector_gate hook error (fail-open): {exc}", file=sys.stderr)
            sys.exit(0)
        print(f"skillspector_gate error: {exc}", file=sys.stderr)
        sys.exit(1)
