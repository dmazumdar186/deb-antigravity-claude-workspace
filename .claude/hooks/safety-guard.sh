#!/bin/bash
# safety-guard.sh
# PreToolUse hook: blocks destructive bash commands before execution.
# Receives tool input as JSON on stdin.
# Exit 0 = allow, Exit 2 = block.

INPUT=$(cat)
CMD=$(echo "$INPUT" | py -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    print(d.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

DANGEROUS=(
  "rm -rf"
  "rm -r /"
  "git push --force"
  "git push -f "
  "git reset --hard"
  "git checkout -- ."
  "git clean -f"
  "DROP TABLE"
  "DROP DATABASE"
  "DELETE FROM"
  "truncate table"
  "format c:"
  "mkfs"
  "dd if="
  ":(){:|:&};"
)

for pattern in "${DANGEROUS[@]}"; do
  if echo "$CMD" | grep -qi "$pattern"; then
    echo "SAFETY-GUARD: Blocked dangerous command matching pattern: \"$pattern\""
    echo "Get explicit user confirmation before proceeding with: $CMD"
    exit 2
  fi
done

exit 0
