#!/bin/bash
# jev-router.sh — UserPromptSubmit hook. Asks Jev (via OpenRouter) which model tier and
# which skill the prompt needs, and injects a one-line routing instruction. Fails open:
# every failure path exits 0 with no output so the prompt is never blocked.
# Toggle with /jev on|off. Details: directives/infrastructure/jev.md
set +e
PY="$(command -v py || command -v python3 || command -v python)"
[ -z "$PY" ] && exit 0
DIR="$(cd "$(dirname "$0")/../.." && pwd)"
[ -f "$DIR/.claude/jev/state.json" ] && grep -q '"enabled": *false' "$DIR/.claude/jev/state.json" && exit 0
cat | "$PY" "$DIR/execution/infrastructure/jev_router.py" hook 2>/dev/null
exit 0
