# Enforcement — git hooks + session hooks (reference)

Moved out of CLAUDE.md (token-economy sweep 2026-09-01). **Effective 2026-08-04.** Rules that used to be text-only are mechanically enforced.

**One-time install after a fresh clone:**
```
bash scripts/install_hooks.sh
```
Sets `git config core.hooksPath .githooks` — points git at the tracked hook dir.

## What runs when

| Trigger | Hook | Blocks? | What it checks |
|---|---|---|---|
| `git commit` | `.githooks/pre-commit` | YES on match | Untracked `.ts/.js/.py/.mjs/.tsx/.jsx/.cjs/.go/.rs` under `functions/`, `worker/`, `workers/`, `pages/api/`, `api/` (any deploy-target dir). Kills the 2026-08-03 yoga_jitendra 13-day-stale-fallback class at commit time. |
| `git push` | `.githooks/pre-push` | YES on HIGH/CRITICAL | Runs `py execution/infrastructure/workspace_sast.py --all --quiet`. Blocks push if any HIGH or CRITICAL finding surfaces (haiku creep, environ-copy, untracked Pages Functions, agent-md frontmatter Haiku, deployed-project-without-front-door, front-door-fixture-only, etc.). |
| Assistant turn ends | `.claude/hooks/verdict-table-check.sh` | Advisory (never blocks) | Greps the assistant's last message for shipped/live/ready/done/complete/wrapped framing. If matched AND < 2 mandatory-audit-stack tools (front-door / acceptance / anneal / panel-pass / pipeline-auditor / adversarial) fired in the recent tool-use window, surfaces a warning to the next turn per ~/.claude/rules/mandatory-audit-stack.md. |

## Emergency bypass (log in HANDOFF.md if used)

- `git commit --no-verify` — bypasses pre-commit.
- `git push --no-verify` — bypasses pre-push.
- The verdict-table hook is already advisory-only; no bypass needed.

When bypassing, add a `**Enforcement bypass**: <one-line reason>` line to `HANDOFF.md` so the choice is auditable. `--no-verify` without a logged reason is a rule violation per `~/.claude/rules/rule-backport-cadence.md`.

## Extending the enforcement

- New SAST rules go in `execution/infrastructure/workspace_sast.py` as `_rule_<name>()` functions and register in `_NATIVE_RULES`. Anything returning severity `high` or `critical` will start blocking pushes on the next commit.
- Hook config lives in `.claude/settings.json` (Stop, PreToolUse, PostToolUse, SessionStart). The `Stop` array holds the verdict-table check alongside the tada notification.
