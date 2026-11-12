---
id: 2026-11-12-hooks-read-stdin-json
triggers: hook, settings.json, posttooluse, pretooluse, formatter, hook script
scope: infra
strength: 1
status: active
created: 2026-11-12
confirmed: 2026-11-12
source: 11b6652
supersedes:
---
Claude Code hooks receive input as JSON on stdin; never read $CLAUDE_TOOL_INPUT_FILE_PATH, which is never set.

Why: 2026-11-12: format-python, note-taker and documenter-prompt hooks had been silent no-ops.
