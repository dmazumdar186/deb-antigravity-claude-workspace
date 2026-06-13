# Settings Notes — 2026 Upgrades

Tracks new keys added to `.claude/settings.json` and `.claude/settings.local.json` as part of the workspace 2026 upgrade. Reference for future debugging and rollback.

## 2026-06-11 — Phase 2 workspace upgrade

Added to `.claude/settings.json` `env` block:

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — opt in to Anthropic's Agent Teams feature. Spawns multiple full Claude sessions coordinated by a team lead with a shared mailbox and task list. Distinct from sub-agents (which only report back to the orchestrator); teammates can claim tasks, message each other, and self-coordinate. Requires Claude Code CLI >= 2.1.154. Installed at time of opt-in: 2.1.173.
- `teammateMode=in-process` — render teammate sessions in the same terminal pane (cycle with Shift+Down). Alternative: `tmux` for split-pane.

Hook events for Agent Teams (`TeammateIdle`, `TaskCreated`, `TaskCompleted`) intentionally NOT registered yet. They'll be wired up the first time Agent Teams is used in a real workflow, to avoid registering hook types the CLI may or may not validate strictly.

### Did NOT change in Phase 2

- `model` key in `.claude/settings.json` — at Phase 2 time (2026-06-11) stayed `claude-opus-4-7` because the global TIME-BOUND MODEL POLICY mandated `claude-fable-5[1m]` for Plan Mode. **Updated 2026-06-13:** `~/.claude/settings.json` `model` is now `claude-opus-4-8`. Reason: Plan-mode default per MODEL POLICY in `~/.claude/CLAUDE.md`. Fable 5 / Mythos 5 are no longer available (2026-06-12 US export-control directive).
- `.claude/settings.local.json` `model` key — file does not exist.

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
