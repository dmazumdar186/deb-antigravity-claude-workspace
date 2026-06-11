# Settings Notes — 2026 Upgrades

Tracks new keys added to `.claude/settings.json` and `.claude/settings.local.json` as part of the workspace 2026 upgrade. Reference for future debugging and rollback.

## 2026-06-11 — Phase 2 workspace upgrade

Added to `.claude/settings.json` `env` block:

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — opt in to Anthropic's Agent Teams feature. Spawns multiple full Claude sessions coordinated by a team lead with a shared mailbox and task list. Distinct from sub-agents (which only report back to the orchestrator); teammates can claim tasks, message each other, and self-coordinate. Requires Claude Code CLI >= 2.1.154. Installed at time of opt-in: 2.1.173.
- `teammateMode=in-process` — render teammate sessions in the same terminal pane (cycle with Shift+Down). Alternative: `tmux` for split-pane.

Hook events for Agent Teams (`TeammateIdle`, `TaskCreated`, `TaskCompleted`) intentionally NOT registered yet. They'll be wired up the first time Agent Teams is used in a real workflow, to avoid registering hook types the CLI may or may not validate strictly.

### Did NOT change in Phase 2

- `model` key in `.claude/settings.json` — stays `claude-opus-4-7`. Reason: the global TIME-BOUND MODEL POLICY (`~/.claude/CLAUDE.md`) mandates `claude-fable-5[1m]` for Plan Mode until 2026-06-21 23:59. Bumping the session default mid-policy invites confusion. Reconsidered post-expiry.
- `.claude/settings.local.json` `model` key — same reason.

## Reverting

To disable Agent Teams: remove the `env` block (or just the two new keys) from `.claude/settings.json`. Restart Claude Code. No other workspace files depend on this opt-in.

## Verification after edit

```powershell
py -c "import json; json.load(open('.claude/settings.json'))"  # should print no errors
claude --version  # should be 2.1.173 or later
```

## Related files

- `.claude/settings.json` — primary config.
- `~/.claude/CLAUDE.md` — global model policy.
- `CLAUDE.md` — workspace Environment section documents the model strategy.
- `.claude/agents/*.md` — per-agent `model:` frontmatter (Sonnet 4.6, Haiku 4.5, Opus 4.7 as appropriate).
