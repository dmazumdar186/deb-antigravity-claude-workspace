# Audit Gate (red-teamed by default, enforced)

## Goal
CLAUDE.md build contract item 3 as a hard block: nothing reaches `main` without a recorded,
HMAC-signed `pipeline-auditor` PASS for that exact code (git tree).

## Inputs
- SubagentStop payload (harness) -> `.claude/hooks/audit-gate.sh` -> `audit_gate.py subagent-hook`.
- `audit_gate.py check <commit> [--repo DIR]` (pre-push, or by hand).
- Env: `AUDIT_DIR` (ledger dir, default `~/.claude/redteam`), `REDTEAM_KEY_FILE`,
  `REDTEAM_TRANSCRIPT_ROOT` (shared with `redteam_gate.py`, whose helpers are imported), `AUDIT_HOOK=1`
  (set only by the wrapper; the hook subcommand refuses without it).

## Tools/Scripts
- `execution/infrastructure/audit_gate.py`
- `.claude/hooks/audit-gate.sh` (SubagentStop wrapper, fails OPEN: never blocks, stderr only)
- `.githooks/pre-push.d/audit-gate` (called from `.githooks/pre-push` after SAST)

## Steps (how a PASS is recorded)
1. Commit the work. Spawn `pipeline-auditor` on it.
2. Its report must contain exactly one `Verdict:` value, `PASS`, and `Audited commit: <sha>`
   (format in `.claude/agents/pipeline-auditor.md`). WARNINGS / FAIL never record; PASS with LOW notes
   records only if the verdict line itself says PASS.
3. The hook accepts only agent type `pipeline-auditor` (or `<plugin>:pipeline-auditor`) with a
   harness transcript `agent-<agent_id>.jsonl` under the transcript root; the report is read from
   `last_assistant_message` or the transcript (incl. `SubagentHandback` input.message).
4. Row `{tree_sha, commit, verdict, ts, agent_id, text_from, mac}` appended to `audits.jsonl`.

## check
Exit 0 when a signed PASS row has the commit's tree, or a PASS commit is an ancestor and every path
changed since is exempt. Exit 1 lists unaudited files; exit 2 unknown commit. Unsigned or tampered
rows are ignored.

Exempt paths ("pure reads and no-logic edits"), deliberately minimal: `docs/**/*.md`,
`.claude/notes/**`, `HANDOFF.md`, `.claude/jev/state.json`. Directives, rules, agent files and
CLAUDE.md are behaviour and are NOT exempt even though they are Markdown.

## Enforcement
Pre-push blocks any update of `refs/heads/main` without coverage. Bypass `git push --no-verify` only
with a `**Enforcement bypass**: <reason>` line in `HANDOFF.md`.

settings.json (SubagentStop):
```json
{"hooks": {"SubagentStop": [{"hooks": [{"type": "command",
  "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/audit-gate.sh\""}]}]}}
```

## Edge Cases
- The auditor names the commit; the gate trusts that it audited that tree (it cannot prove what the
  auditor read). Uncommitted edits are never covered.
- The ledger and key are per-machine (`~/.claude`): a cloud clone or another machine has no rows, so
  its pushes to main block until audited there.
- Merge commits get a new tree: re-audit, unless the merge only adds exempt paths over an audited
  ancestor.
- Server-side bypass (GitHub web merge, `--no-verify`) is outside the hook; pair with branch rules.

## Outputs
Signed rows in `$AUDIT_DIR/audits.jsonl`; `check` exit code + unaudited file list on stdout.

## Output contract
Machine state only (`audits.jsonl`, stderr lines); nothing goes into human deliverables.

## Tests
`python3 -m pytest -q tests/test_audit_gate.py`
