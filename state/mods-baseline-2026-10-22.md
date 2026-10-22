# Mods rollout baseline — 2026-10-22

Branch `mods-rollout`. CLI `claude --version` = 2.1.308 (floor 2.1.287, no upgrade needed).
Cloud session (claude.ai/code, Linux container); `.claude/mods/` is symlinked into the
session's hot-reload folder `~/.claude/dev-mods/<session>/`.

## Active hooks in `.claude/settings.json` before cutover

| Event | Matcher | Script |
|---|---|---|
| PreToolUse | Bash | `.claude/hooks/safety-guard.sh` |
| PreToolUse | AskUserQuestion | `.claude/hooks/notify-done.sh Alarm01.wav` |
| PostToolUse | AskUserQuestion | `.claude/hooks/notify-done.sh Alarm01.wav` |
| PostToolUse | Edit\|Write | `.claude/hooks/note-taker.sh` (async) |
| PostToolUse | Edit\|Write | `.claude/hooks/format-python.sh` |
| PostToolUse | Edit\|Write | `.claude/hooks/documenter-prompt.sh` (async) |
| SessionStart | — | `.claude/hooks/session-start.sh` |
| Stop | — | `.claude/hooks/notify-done.sh tada.wav` |
| Stop | — | `.claude/hooks/verdict-table-check.sh` |
| Notification | — | `.claude/hooks/notify-done.sh Alarm01.wav` |
| UserPromptSubmit | — | `.claude/hooks/jev-router.sh` |

## `/cost` and `/context` at baseline

unknown — slash commands render in the operator's client only; the model cannot invoke
them from a cloud session. Proxy: the session's context budget reported by the harness at
preflight was ~15.0M tokens remaining of the session allowance; no per-turn cost figure
is exposed. Context Meter's eval row therefore compares against `$.session.usage()`
(the same source `/context` reads) rather than a `/context` screenshot.

## HITL count, last 3 sessions

unknown — `.claude/handoffs/` holds one handoff (2026-06-15) and no session logs are
retained in the cloud container; neither records permission prompts or AskUserQuestion
calls. `permissions.defaultMode` was `bypassPermissions`, so permission prompts were 0 by
construction; AskUserQuestion calls are not derivable.

## Session start time

`session-start.sh` wall clock, measured once: 138 ms (hook alone; the client's own
launch-to-first-prompt time is not observable from inside the container).

## Community mods (whyashthakker/awesome-claude-code-mods, cloned at HEAD 2026-10-22)

| Mod | Verdict |
|---|---|
| Context Meter | PASS — reads `$.session.usage()` only; no `$.http`, `$.process`, `$.fs`, store, or permission answers. Installed. |
| Quota Watch | PASS — reads `$.session.usage()` rate-limit windows only; no network, no permission answers. Installed. |
| Tool Timing | PASS — observes `tool.call` names, results and `$.clock`; stores no arguments; no network, no permission answers. Installed. |
