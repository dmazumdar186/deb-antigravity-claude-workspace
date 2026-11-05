#!/usr/bin/env bash
# .claude/hooks/redteam-outward-gate.sh
#
# Red-team gate for outward text. Usage: redteam-outward-gate.sh pre|post|subagent|prompt
#   pre      -> PreToolUse (Gmail send/reply/forward/drafts, Calendar create/update_event,
#               MCP share/permission/post/send/publish tools, Bash):
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
# Share/permission/post/send/publish MCP tools (any server) fail closed too, except reads.
if printf '%s' "$INPUT" | grep -Eiq '"tool_name"[[:space:]]*:[[:space:]]*"mcp__[^"]*__[^"]*(share|permission|post_message|send_|publish)' \
   && ! printf '%s' "$INPUT" | grep -Eiq '"tool_name"[[:space:]]*:[[:space:]]*"mcp__[^"]*__(get|list|search|read|resolve|download|fetch|describe|find|query|lookup|check|count|export|delete|remove|revoke|unshare|trash|untrash)_?'; then
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
