"""
audit_gate.py
description: Hard gate for CLAUDE.md build-contract item 3 (red-teamed by default). Records signed
  pipeline-auditor PASS verdicts from SubagentStop and blocks pushes to main whose tree has none.
inputs: subcommands subagent-hook (SubagentStop JSON on stdin; needs env AUDIT_HOOK=1) |
  check <commit> [--repo DIR]; env AUDIT_DIR (ledger dir, default ~/.claude/redteam),
  REDTEAM_KEY_FILE / REDTEAM_TRANSCRIPT_ROOT (shared with redteam_gate.py).
outputs: signed rows in <AUDIT_DIR>/audits.jsonl; check exits 0 (audited) / 1 (unaudited) / 2 (usage).
directive: directives/infrastructure/audit_gate.md

Rules:
* Only agents whose type is pipeline-auditor (or <plugin>:pipeline-auditor) count, and only when
  the harness-written transcript agent-<agent_id>.jsonl exists under the transcript root.
* The report must have exactly one distinct `Verdict:` value and it must be PASS (WARNINGS/FAIL never
  record), plus an `Audited commit: <sha>` line that resolves to a commit in the payload cwd repo.
* check passes when a signed PASS row's tree equals the commit's tree, or a PASS commit is an
  ancestor and every path changed since it is exempt (pure reads and no-logic edits; EXEMPT below).
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import redteam_gate as rg  # noqa: E402  (HMAC key, sign/verify, transcript checks)

AUDITOR_AGENT = "pipeline-auditor"
AUDITS = "audits.jsonl"
# Pure reads and no-logic edits (CLAUDE.md item 3 exemption). Deliberately minimal: directives,
# agent files, rules and CLAUDE.md change behaviour, so they are NOT exempt even though they are .md.
EXEMPT = ("docs/*.md", "docs/**/*.md", ".claude/notes/*", ".claude/notes/**",
          "HANDOFF.md", ".claude/jev/state.json")

_VERDICT_RE = re.compile(r"^[\s>*_#-]*verdict\s*[:\-]\s*\**\s*([A-Za-z]+)", re.I | re.M)
_COMMIT_RE = re.compile(r"^[\s>*_#-]*(?:audited\s+commit|head(?:\s+commit)?)\s*[:=]\s*\**\s*`?"
                        r"([0-9a-f]{7,40})\b", re.I | re.M)


def audit_dir() -> Path:
    env = os.environ.get("AUDIT_DIR", "").strip()
    return Path(env).expanduser() if env else Path.home() / ".claude" / "redteam"


def _git(repo: str | Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def is_auditor(agent_type: Any) -> bool:
    return isinstance(agent_type, str) and (agent_type == AUDITOR_AGENT
                                            or agent_type.endswith(":" + AUDITOR_AGENT))


def parse_report(text: str) -> tuple[str | None, str | None]:
    """(verdict, commit-ish). verdict is None unless exactly one distinct value is stated."""
    verdicts = {m.group(1).upper() for m in _VERDICT_RE.finditer(text)}
    commits = {m.group(1).lower() for m in _COMMIT_RE.finditer(text)}
    verdict = verdicts.pop() if len(verdicts) == 1 else None
    commit = commits.pop() if len(commits) == 1 else None
    return verdict, commit


def cmd_subagent_hook(_args: argparse.Namespace) -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict) or not is_auditor(payload.get("agent_type")):
            return 0
        text, origin = rg.subagent_final_text(payload)  # enforces agent-<id>.jsonl under root
        if not text.strip():
            return 0
        verdict, commitish = parse_report(text)
        if verdict != "PASS" or not commitish:
            print(f"audit-gate: no PASS row (verdict={verdict}, commit={commitish})", file=sys.stderr)
            return 0
        repo = payload.get("cwd") or os.getcwd()
        commit = _git(repo, "rev-parse", "--verify", "--quiet", f"{commitish}^{{commit}}")
        tree = commit and _git(repo, "rev-parse", f"{commit}^{{tree}}")
        if not commit or not tree:
            print(f"audit-gate: commit {commitish} not found in {repo}", file=sys.stderr)
            return 0
        rg._append_jsonl(audit_dir() / AUDITS, {
            "tree_sha": tree, "commit": commit, "verdict": "PASS", "ts": rg._now(),
            "agent_id": str(payload.get("agent_id") or ""), "text_from": origin})
        print(f"audit-gate: recorded PASS for {commit[:12]}", file=sys.stderr)
    except Exception as exc:  # never block a SubagentStop; a missing row only makes check fail
        print(f"audit-gate subagent-hook error: {type(exc).__name__}", file=sys.stderr)
    return 0


def is_exempt(path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, pat) for pat in EXEMPT)


def pass_rows() -> list[dict]:
    rows, ignored = rg.read_signed(audit_dir() / AUDITS)
    if ignored:
        print(f"audit-gate: ignored {ignored} unsigned/tampered row(s)", file=sys.stderr)
    return [r for r in rows if r.get("verdict") == "PASS" and isinstance(r.get("tree_sha"), str)
            and isinstance(r.get("commit"), str)]


def check(commit: str, repo: str | Path = ".") -> tuple[bool, list[str]]:
    """(ok, unaudited files for the closest audited ancestor, or all files if none)."""
    sha = _git(repo, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
    if not sha:
        raise rg.UsageError(f"unknown commit {commit}")
    tree = _git(repo, "rev-parse", f"{sha}^{{tree}}")
    rows = pass_rows()
    if any(r["tree_sha"] == tree for r in rows):
        return True, []
    best: list[str] | None = None
    for r in rows:
        if _git(repo, "merge-base", "--is-ancestor", r["commit"], sha) is None:
            continue
        diff = _git(repo, "diff", "--name-only", "--no-renames", r["commit"], sha)
        if diff is None:
            continue
        bad = [p for p in diff.splitlines() if p and not is_exempt(p)]
        if not bad:
            return True, []
        if best is None or len(bad) < len(best):
            best = bad
    if best is None:
        best = [p for p in (_git(repo, "ls-tree", "-r", "--name-only", sha) or "").splitlines()
                if not is_exempt(p)]
        best = best[:50] + ([f"... (no audited ancestor; {len(best)} files)"] if len(best) > 50
                            else [])
    return False, best


def cmd_check(args: argparse.Namespace) -> int:
    try:
        ok, bad = check(args.commit, args.repo)
    except rg.UsageError as exc:
        print(f"audit-gate: {exc}", file=sys.stderr)
        return 2
    if ok:
        print(f"audit-gate: {args.commit} is covered by a signed pipeline-auditor PASS")
        return 0
    print(f"audit-gate: {args.commit} has no signed pipeline-auditor PASS. Unaudited files:")
    for p in bad:
        print(f"  {p}")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("subagent-hook")
    c = sub.add_parser("check")
    c.add_argument("commit")
    c.add_argument("--repo", default=".")
    args = ap.parse_args(argv)
    if args.cmd == "subagent-hook":
        if os.environ.get("AUDIT_HOOK") != "1":
            print("audit-gate: subagent-hook is harness-only (run by .claude/hooks/audit-gate.sh)",
                  file=sys.stderr)
            return 2
        return cmd_subagent_hook(args)
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
