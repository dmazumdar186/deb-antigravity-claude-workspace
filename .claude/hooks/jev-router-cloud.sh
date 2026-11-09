#!/bin/bash
# jev-router-cloud.sh — UserPromptSubmit fallback for cloud sessions only.
# Locally the jev-router-mod plugin routes prompts; it does not load in Claude Code on the web,
# so this hook runs the same router there. No-op unless CLAUDE_CODE_REMOTE=true, so a local
# session never routes twice. Fails open: always exit 0, never blocks a prompt.
# Toggle with /jev on|off. Details: directives/infrastructure/jev.md
set +e
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
PY="$(command -v python3 || command -v python)"
[ -z "$PY" ] && exit 0
DIR="$(cd "$(dirname "$0")/../.." && pwd)"
[ -f "$DIR/.claude/jev/state.json" ] && grep -q '"enabled": *false' "$DIR/.claude/jev/state.json" && exit 0
cat | "$PY" "$DIR/execution/infrastructure/jev_router.py" hook 2>/dev/null
exit 0
