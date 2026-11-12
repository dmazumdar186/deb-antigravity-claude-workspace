#!/bin/bash
# brain.sh — workspace brain hooks (directives/infrastructure/brain.md).
#   $1 = start  (SessionStart: core lessons + upkeep flag)
#   $1 = prompt (UserPromptSubmit: lessons matching this prompt; correction reminder)
#   $1 = stop   (Stop: block once if a miss was admitted but not recorded)
# Offline and deterministic on every prompt (no network). Fails open: always exit 0.
set +e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "" >/dev/null 2>&1; then
    "$c" "$DIR/execution/infrastructure/brain.py" "hook-${1:-prompt}" 2>/dev/null
    exit 0
  fi
done
exit 0
