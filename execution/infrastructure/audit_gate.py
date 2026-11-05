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
EXEMPT = ("docs/*.md", "docs/**/*.md", ".claude/notes/*.md", ".claude/notes/**/*.md",
          "HANDOFF.md", ".claude/jev/state.json")

# Any line labelled Verdict (plain, **Verdict:**, **Verdict**:, list/quote/heading prefixes).
_VERDICT_LINE_RE = re.compile(r"^[\s>#*_-]*\**\s*verdict\s*\**\s*:(.*)$", re.I | re.M)
# The only accepted value: exactly PASS, optionally wrapped in ** (nothing else on the line).
_PASS_VALUE_RE = re.compile(r"[\s*]*PASS[\s*]*")
_COMMIT_RE = re.compile(r"^[\s>#*_-]*\**\s*audited\s+commit\s*\**\s*[:=]"
                        r"\s*\**\s*`?([0-9a-f]{7,40})`?\s*\**\s*$", re.I | re.M)


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
    """(verdict, commit-ish). verdict is "PASS" only when there is exactly one Verdict line and its
    value is exactly PASS (no "/", no "(with warnings)"); otherwise the raw value or None."""
    values = [m.group(1).strip() for m in _VERDICT_LINE_RE.finditer(text)]
    commits = sorted({m.group(1).lower() for m in _COMMIT_RE.finditer(text)}, key=len)
    # Prefix-equal shas name the same commit; anything else is ambiguous.
    commit = (commits[-1] if commits and all(commits[-1].startswith(c) for c in commits)
              else None)
    if len(values) != 1:
        return None, commit
    v = values[0]
    return ("PASS" if _PASS_VALUE_RE.fullmatch(v) and "/" not in v else v), commit


def report_text(payload: dict) -> tuple[str, str]:
    """Final report: whichever of the transcript (incl. SubagentHandback) and last_assistant_message
    carries a Verdict line, transcript first. Requires the harness transcript (agent-<id>.jsonl)."""
    tp = rg.agent_transcript(payload)
    if tp is None:
        return "", ""
    cands = [(rg.transcript_final_text(tp, str(payload["agent_id"]), False), "agent_transcript_path"),
             (rg._content_text(payload.get("last_assistant_message")), "last_assistant_message")]
    for text, origin in cands:
        if _VERDICT_LINE_RE.search(text or ""):
            return text, origin
    return "", ""


def cmd_subagent_hook(_args: argparse.Namespace) -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict) or not is_auditor(payload.get("agent_type")):
            return 0
        text, origin = report_text(payload)
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


MAX_MERGE_DEPTH = 64


def merge_tree_supported(repo: str | Path) -> bool:
    out = _git(repo, "version") or ""
    m = re.search(r"(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (2, 38)


def _merge_ok(repo: str | Path, sha: str, tree: str, rows: list[dict], depth: int) -> bool:
    """A 2-parent merge is covered when both parents are covered and the merge introduced no
    manual change: a clean `git merge-tree --write-tree p1 p2` reproduces its tree exactly."""
    parents = (_git(repo, "rev-list", "--parents", "-n", "1", sha) or "").split()[1:]
    if len(parents) != 2 or depth >= MAX_MERGE_DEPTH or not merge_tree_supported(repo):
        return False  # octopus / root / too deep / old git: deny
    auto = _git(repo, "merge-tree", "--write-tree", parents[0], parents[1])  # None on conflict
    if not auto or auto.splitlines()[0].strip() != tree:
        return False
    return all(_check(p, repo, rows, depth + 1)[0] for p in parents)


def check(commit: str, repo: str | Path = ".") -> tuple[bool, list[str]]:
    """(ok, unaudited files for the closest audited ancestor, or all files if none)."""
    return _check(commit, repo, pass_rows(), 0)


def _check(commit: str, repo: str | Path, rows: list[dict], depth: int) -> tuple[bool, list[str]]:
    sha = _git(repo, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
    if not sha:
        raise rg.UsageError(f"unknown commit {commit}")
    tree = _git(repo, "rev-parse", f"{sha}^{{tree}}")
    if any(r["tree_sha"] == tree for r in rows):
        return True, []
    if _merge_ok(repo, sha, tree or "", rows, depth):
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
