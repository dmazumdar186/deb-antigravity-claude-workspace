# Code review: Boris Cherny's plugin vs this workspace (2026-10-17)

## What Boris uses
- **Mar 2026** he announced "Claude Code: Code Review", a team of agents on every PR, built for the Claude Code team first. Source: `anthropics/claude-code/plugins/code-review` (author field: Boris Cherny), 7.3 KB command file.
- **Jan 2026** the team runs most review on CI via the Agent SDK so a human reads code that is already clean.
- **Aug/Sep 2026** he describes the day-to-day form as the built-in `/code-review`, `/code-review low`, `/code-review medium`: adversarial review as a one-line prompt. That built-in skill ships in Claude Code CLI 2.1.173+ and is available in this workspace at zero prefix cost.

## What the plugin does (the transferable design)
1. Skip gate: closed, draft, trivial, already-reviewed PRs.
2. Scope CLAUDE.md compliance to files on the same path as the change.
3. Summarize the PR once, then 4 parallel reviewers (2 compliance, 2 bug hunters) that see only the diff.
4. **Generate, then validate**: every finding goes to a second agent whose only job is to confirm it. Unconfirmed findings are dropped.
5. **High-signal rule**: report only won't-compile, definitely-wrong-output, or a quotable rule violation. Explicit false-positive list (pre-existing, looks-wrong-but-correct, nits, linter-catchable, input-dependent, silenced).
6. Posts one inline comment per issue, committable suggestion only when it fixes the issue entirely.

## Comparison with our stack
| | Boris plugin | Built-in `/code-review` | Ours (before) |
|---|---|---|---|
| Prefix cost | plugin command 7.3 KB | 0 (built-in) | `agent-review` 2.5 KB + `code-reviewer` 4.9 KB |
| Models | Haiku + Sonnet + Opus (Haiku banned here) | effort levels | `opus` alias in `agent-review` (violates pin-full-ID rule) |
| Scope | PR via `gh` only | diff, PR, branch, or path | file list |
| False-positive control | validate pass + 80 confidence | effort level | "self-verify" paragraph |
| Workspace rules (AuthorizedSession, `chr(65+n)`, bulk-delete safety) | only via CLAUDE.md | no | `code-reviewer` Step 3 |

## Decision
- **Use the built-in `/code-review low`** for every diff-level review. It is Boris's own daily tool and is lighter than anything we carry. `/code-review --fix` replaces the Implement → Review → Resolve chain.
- **Archived** `.claude/skills/agent-review` to `docs/reference/skills-archive/` (demo-library skill, duplicated the built-in, used a model alias).
- **Kept** `code-reviewer` for workspace-specific forbidden patterns and data-safety checks, with the plugin's validate-then-report rule and false-positive list folded in (Step 5).
- **Not installed**: the plugin itself (PR-only, uses Haiku, 7.3 KB of prefix for a worse scope than the built-in).
- `anneal-reviewer`, `pipeline-auditor`, `qa` are unaffected: they check Windows hardening, outcomes, and runtime contracts, which no generic reviewer covers.

## Audit stack wording
"Run the audit stack" on code changes now means: `/code-review low` (built-in) → `code-reviewer` (workspace rules) → `anneal-reviewer` → `pipeline-auditor` where outcomes exist, fired in one batch.
