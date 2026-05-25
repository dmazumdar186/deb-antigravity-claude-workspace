# Workspace SAST Pre-pass

A deterministic pre-pass that catches common bugs in `execution/` Python scripts before the LLM audit (anneal) or before a commit. Runs ruff (style + security) and semgrep (deep semantic patterns) over changed or specified files and emits a markdown severity report.

## Goal

Shift bug detection left: catch hardcoded secrets, unused imports, insecure subprocess calls, and known vulnerability patterns *before* spending LLM tokens on an audit round. The pre-pass is cheap (< 5 s on typical diffs) and deterministic, so it catches the same class of bugs every time without relying on model judgment.

## When to Run

| Trigger | Mode | Command |
|---------|------|---------|
| After every edit to `execution/` (Claude Code hook) | changed files | automatic via PostToolUse hook |
| Before opening a PR | all files | `py execution/infrastructure/workspace_sast.py --all` |
| On a specific file or diff | explicit list | `py execution/infrastructure/workspace_sast.py --files <f1> <f2>` |
| Default (git diff HEAD) | changed files | `py execution/infrastructure/workspace_sast.py --changed` |

## Inputs

| Input | Source |
|-------|--------|
| Python files to scan | `--changed` (git diff HEAD filtered to `execution/*.py`), `--all` (walk `execution/`), or `--files <list>` |
| ruff executable | PATH (or anneal's bundled runner) |
| semgrep executable | PATH (or anneal's bundled runner) |

No API keys, no network calls, no paid resources.

## Tools / Scripts

| Reference | Purpose |
|-----------|---------|
| `execution/infrastructure/workspace_sast.py` | The runner — this directive's paired script |
| `C:/Users/deban/dev/anneal/src/anneal/sast/` | Anneal's RuffRunner, SemgrepRunner, CompositeSastRunner (reused via try-import) |
| `directives/infrastructure/canary_monitoring.md` | Companion directive for deployed-service canary probes |

## Outputs

Markdown report to stdout. Example:

```
## Workspace SAST report
Scanned: 12 files
Findings: 3 (critical: 0, high: 1, medium: 2, low: 0)

### high — execution/foo.py:42 [ruff:S105]
Possible hardcoded password

### medium — execution/bar.py:88 [ruff:F401]
`os` imported but unused
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | No critical or high findings (clean or only medium/low/info) |
| 1 | At least one critical or high finding — should fix before merge |
| 2 | Neither ruff nor semgrep is installed |

## Severity Policy

| Severity | Policy | Action |
|----------|--------|--------|
| `critical` | Must fix before merge | Block the commit / PR |
| `high` | Should fix before merge | Fix or add a PR comment explaining the defer |
| `medium` | Judgment call | Safe to defer; log the debt |
| `low` | Judgment call | Noise-level; fix opportunistically |
| `info` | Informational only | Ignore unless you have time |

Ruff severity mapping (prefix of rule ID):
- `S*` (bandit/security) → **high**
- `E*`, `W*` (pycodestyle) → **medium**
- `F*` (pyflakes) → **low**
- everything else → **info**

Semgrep severity mapping: `ERROR` → high, `WARNING` → medium, `INFO` → low.

## Suppression

Suppress a specific finding inline rather than globally:

```python
password = "hunter2"  # noqa: S105  — test fixture, not a real secret
import os  # noqa: F401  — re-exported for callers
```

For semgrep: `# nosemgrep: <rule-id>`.

If a rule consistently fires as a false positive for this codebase, add a filter in the runner or a `ruff.toml` / `semgrep.yml` at the workspace root.

## Hook Behavior

A Claude Code `PostToolUse` hook fires after every `Edit` or `Write` tool call and runs `--changed` mode. The hook is in `.claude/settings.local.json`.

**Current mode: warn-only.** The hook appends `|| true` so it never blocks the edit, even if findings exist. Findings are surfaced to stdout as context for the next audit round.

### Escalating from warn to enforce

After 1–2 weeks of warn-mode:
1. Review false-positive rate. If < 10% of `high` findings are false positives, escalate.
2. Remove `|| true` from the hook command in `.claude/settings.local.json`.
3. Add `"exit_on_nonzero": true` (or equivalent) to the hook entry.
4. Document the escalation date in this directive's changelog.

## AM Lockdown

The runner automatically skips any path matching `*accessory*`, `*hedgestone*`, `*elite-broker*`, `*elitebrokergroup*` (case-insensitive), per the workspace lockdown policy in `CLAUDE.local.md`.

## Steps

1. **Identify files to scan.** Depends on mode: git diff, directory walk, or explicit list.
2. **Try anneal import.** `sys.path.insert(0, anneal_src)` → import `CompositeSastRunner`, `RuffRunner`, `SemgrepRunner`. On failure, fall back to subprocess.
3. **Run tools.** Anneal path delegates to `CompositeSastRunner.run(worktree, rel_files)`. Subprocess path shells out to `ruff check --output-format=json` and `semgrep scan --json`.
4. **Aggregate findings.** Deduplicate by `(file, line, rule_id)`.
5. **Render report.** Sort by severity order; emit markdown to stdout.
6. **Exit.** 0 = clean or warn-only, 1 = critical/high found, 2 = no tools.

## Edge Cases

- **ruff/semgrep not installed:** runner exits 2 with a human-readable message — no crash, no missing message.
- **Empty diff:** exits 0 with "no Python files to scan" and no report noise.
- **Absolute vs relative paths:** anneal runners expect relative-to-worktree paths; the script converts absolute paths before delegating.
- **subprocess encoding:** all `subprocess.run` calls use `encoding="utf-8", errors="replace"` per the workspace hardening rules.
- **AM-locked paths:** silently skipped; never pass through to any tool call.
- **Anneal import failure:** graceful fall-through to subprocess mode; no exception propagates to the user.
- **Semgrep `--config=auto` network call:** semgrep may download rules on first run if not cached. Subsequent runs use the local cache. This is expected behavior.

## Reference to Anneal

Anneal v0.1 ships the same runners at `C:/Users/deban/dev/anneal/src/anneal/sast/`. This workspace runner imports them via try-import for zero code duplication. If anneal is updated (e.g. new runner added), the workspace pre-pass benefits automatically on the next run.

## Changelog

- **2026-05-25** — Initial version. try-import anneal path + subprocess fallback. Warn-mode hook in `.claude/settings.local.json`. AM-lockdown guard applied.
