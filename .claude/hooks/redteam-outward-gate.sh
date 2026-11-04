#!/usr/bin/env bash
# .claude/hooks/redteam-outward-gate.sh
#
# Red-team gate for outward text. Usage: redteam-outward-gate.sh pre|post|subagent|prompt
#   pre      -> PreToolUse (Gmail send/reply/forward/drafts, Calendar create/update_event, Bash):
#               redteam_gate.py hook. FAIL-CLOSED: missing python/script or a non-zero exit
#               prints a deny JSON. An error here must never let an email through.
#   post     -> PostToolUse (Gmail create/update_draft): redteam_gate.py post-hook. Never blocks,
#               no stdout.
#   subagent -> SubagentStop: redteam_gate.py subagent-hook (logs lens verdicts to the
#               hook-owned verdicts.jsonl). Never blocks, no stdout.
#   prompt   -> UserPromptSubmit: redteam_gate.py prompt-hook (operator waiver
#               `redteam waive <sha12> <reason>`). Never blocks; stdout is the script's
#               additionalContext JSON or nothing.
# Directive: directives/infrastructure/redteam_gate.md
set +e

MODE="${1:-pre}"
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SCRIPT="$ROOT/execution/infrastructure/redteam_gate.py"
PY="$(command -v python3 || command -v python || command -v py)"

deny() {
  printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"redteam gate error (fail-closed): $1\"}}"
  exit 0
}

INPUT="$(cat)"

case "$MODE" in
  post|subagent|prompt)
    case "$MODE" in
      post) SUB="post-hook" ;;
      subagent) SUB="subagent-hook" ;;
      prompt) SUB="prompt-hook" ;;
    esac
    if [ -n "$PY" ] && [ -f "$SCRIPT" ]; then
      OUT="$(printf '%s' "$INPUT" | "$PY" "$SCRIPT" "$SUB" 2>/dev/null)"
      [ "$MODE" = "prompt" ] && [ -n "$OUT" ] && printf '%s\n' "$OUT"
    fi
    exit 0
    ;;
  pre) ;;
  *) deny "unknown mode" ;;
esac

[ -n "$PY" ] || deny "python not found"
[ -f "$SCRIPT" ] || deny "redteam_gate.py not found"

OUT="$(printf '%s' "$INPUT" | "$PY" "$SCRIPT" hook 2>/dev/null)"
RC=$?
[ "$RC" -eq 0 ] || deny "gate script exit $RC"
[ -n "$OUT" ] && printf '%s\n' "$OUT"
exit 0
