#!/bin/bash
# documenter-prompt.sh
# PostToolUse hook: fires after Edit|Write on execution/**/*.py files.
# Reminds Claude to spawn the Documenter sub-agent to sync the corresponding
# directive. This is a REMINDER only — it never spawns the agent automatically
# (that would consume tokens on every edit).
#
# Configured in .claude/settings.json as an async PostToolUse hook.
# Always exits 0 — must never block edits.

set +e

FILE_PATH="${1:-$CLAUDE_TOOL_INPUT_FILE_PATH}"

# Only fire for Python files under execution/
if [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi

if [[ "$FILE_PATH" != *"execution/"* ]] && [[ "$FILE_PATH" != *"execution\\"* ]]; then
  exit 0
fi

# Skip AM-locked paths (safety belt)
lower_path="${FILE_PATH,,}"
for pattern in "accessory" "hedgestone" "elite-broker" "elitebrokergroup"; do
  if [[ "$lower_path" == *"$pattern"* ]]; then
    exit 0
  fi
done

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  DOCUMENTER REMINDER                                              ║"
echo "║  execution/ script was edited — sync the directive next.         ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  File: $FILE_PATH"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Spawn this sub-agent when done with the script:                 ║"
echo "║                                                                   ║"
echo "║  Agent(                                                           ║"
echo "║    subagent_type='general-purpose',                               ║"
echo "║    description='Sync directive after script edit',               ║"
echo "║    prompt=(                                                       ║"
echo "║      'Read directives/subagent/documenter.md and follow its      ║"
echo "║       instructions. Script updated: [NAME]. Changes: [DESC]'     ║"
echo "║    )                                                              ║"
echo "║  )                                                                ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

exit 0
