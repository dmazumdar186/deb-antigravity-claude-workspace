#!/usr/bin/env bash
# .claude/hooks/audit-gate.sh — SubagentStop: record signed pipeline-auditor PASS verdicts.
# FAILS OPEN: never blocks, never prints to stdout; errors go to stderr.
# Directive: directives/infrastructure/audit_gate.md
set +e
export AUDIT_HOOK=1
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SCRIPT="$ROOT/execution/infrastructure/audit_gate.py"
PY="$(command -v python3 || command -v python || command -v py)"
INPUT="$(cat)"
if [ -z "$PY" ] || [ ! -f "$SCRIPT" ]; then
  echo "audit-gate: python or audit_gate.py missing; not recorded" >&2
  exit 0
fi
printf '%s' "$INPUT" | "$PY" "$SCRIPT" subagent-hook >/dev/null
exit 0
