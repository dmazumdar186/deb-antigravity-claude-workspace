#!/usr/bin/env bash
# .claude/hooks/redteam-outward-gate.sh
#
# Red-team gate for outward text (Gmail MCP tools). Usage: redteam-outward-gate.sh pre|post
#   pre  -> PreToolUse  : execution/infrastructure/redteam_gate.py hook
#           Denies send_message / reply / forward / create_draft / update_draft unless every
#           outward text field's normalised sha is in .tmp/redteam/passes.jsonl.
#   post -> PostToolUse : execution/infrastructure/redteam_gate.py post-hook
#           Records draft id -> text sha in .tmp/redteam/drafts.jsonl (never blocks).
#
# FAIL-CLOSED (pre): if python is missing, the script is missing, or it exits non-zero, a deny
# JSON is printed. Unlike skillspector-gate.sh, an error here must never let an email through.
# Directive: directives/infrastructure/redteam_gate.md
set +e

MODE="${1:-pre}"
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SCRIPT="$ROOT/execution/infrastructure/redteam_gate.py"
PY="$(command -v py || command -v python3 || command -v python)"

deny() {
  printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"redteam gate error (fail-closed): $1\"}}"
  exit 0
}

INPUT="$(cat)"

if [ "$MODE" = "post" ]; then
  [ -n "$PY" ] && [ -f "$SCRIPT" ] && printf '%s' "$INPUT" | "$PY" "$SCRIPT" post-hook >/dev/null 2>&1
  exit 0
fi

[ "$MODE" = "pre" ] || deny "unknown mode"
[ -n "$PY" ] || deny "python not found"
[ -f "$SCRIPT" ] || deny "redteam_gate.py not found"

OUT="$(printf '%s' "$INPUT" | "$PY" "$SCRIPT" hook 2>/dev/null)"
RC=$?
[ "$RC" -eq 0 ] || deny "gate script exit $RC"
[ -n "$OUT" ] && printf '%s\n' "$OUT"
exit 0
