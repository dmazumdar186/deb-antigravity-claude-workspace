#!/usr/bin/env bash
# .claude/hooks/redteam-outward-gate.sh
#
# Red-team gate for outward text. Usage: redteam-outward-gate.sh pre|post|subagent|prompt
#   pre      -> PreToolUse (Gmail send/reply/forward/drafts, Calendar create/update_event,
#               every other MCP tool (the gate decides; reads pass), Bash):
#               redteam_gate.py hook. FAIL-CLOSED for OUTWARD tools only (Gmail/Calendar):
#               missing python/script or a crash denies them. For Bash and any other tool a
#               crash ALLOWS and logs to stderr, so a broken gate can never brick a session.
#   post     -> PostToolUse (Gmail create/update_draft): redteam_gate.py post-hook. Never blocks,
#               no stdout.
#   subagent -> SubagentStop: redteam_gate.py subagent-hook (logs lens verdicts, HMAC-signed).
#               Never blocks, no stdout.
#   prompt   -> UserPromptSubmit: redteam_gate.py prompt-hook (operator waiver
#               `redteam waive <sha12> <reason>`). Never blocks; stdout is the script's
#               additionalContext JSON or nothing.
# Directive: directives/infrastructure/redteam_gate.md
set +e
export REDTEAM_HOOK=1

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

OUTWARD=0
if printf '%s' "$INPUT" | grep -Eq '"tool_name"[[:space:]]*:[[:space:]]*"mcp__[^"]*([Gg]mail|[Cc]alendar|send_email|send_message|create_draft)'; then
  OUTWARD=1
fi
# Structural rule (mirrors mcp_outward_kind): every MCP tool fails closed unless it is
# harness-internal or its tool segment starts with a read verb / local action.
if printf '%s' "$INPUT" | grep -Eiq '"tool_name"[[:space:]]*:[[:space:]]*"mcp__' \
   && ! printf '%s' "$INPUT" | grep -Eiq '"tool_name"[[:space:]]*:[[:space:]]*"mcp__(claude-code-remote|ccd_session)__' \
   && ! { printf '%s' "$INPUT" | grep -Eq '"tool_name"[[:space:]]*:[[:space:]]*"mcp__([^"_]|_[^"_])*__(get|list|search|read|fetch|download|query|resolve|describe|view|count|check|suggest|lookup|find|delete|trash|untrash|label|unlabel|mark|unmark|archive|apply|remove|revoke|unshare)(_|[A-Z]|")' \
          && ! printf '%s' "$INPUT" | grep -Eiq '"tool_name"[[:space:]]*:[[:space:]]*"mcp__([^"_]|_[^"_])*__[^"]*(send|post|share|publish|reply|forward|comment|tweet|message|create|update|write|invite|upload|schedule|_and_|_then_|And[A-Z]|Then[A-Z])'; }; then
  OUTWARD=1
fi

fail() {
  if [ "$OUTWARD" -eq 1 ]; then deny "$1"; fi
  printf 'redteam gate error (non-outward tool allowed): %s\n' "$1" >&2
  exit 0
}

[ -n "$PY" ] || fail "python not found"
[ -f "$SCRIPT" ] || fail "redteam_gate.py not found"

ERRF="$(mktemp 2>/dev/null || echo "/tmp/redteam_gate_err.$$")"
OUT="$(printf '%s' "$INPUT" | "$PY" "$SCRIPT" hook 2>"$ERRF")"
RC=$?
if [ "$RC" -ne 0 ]; then
  head -c 2000 "$ERRF" >&2 2>/dev/null
  rm -f "$ERRF"
  fail "gate script exit $RC"
fi
rm -f "$ERRF"
[ -n "$OUT" ] && printf '%s\n' "$OUT"
exit 0
