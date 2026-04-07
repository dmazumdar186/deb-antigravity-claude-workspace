#!/bin/bash
# note-taker.sh
# Fires after edits to directives/ or execution/ files.
# Reminds Claude to capture any new learnings to .claude/notes/.
#
# Configured in .claude/settings.json as a PostToolUse hook for Write/Edit tools.

FILE_PATH="${1:-}"

if [[ "$FILE_PATH" == *"directives/"* ]] || [[ "$FILE_PATH" == *"directives\\"* ]] || \
   [[ "$FILE_PATH" == *"execution/"* ]]  || [[ "$FILE_PATH" == *"execution\\"* ]]; then
  echo "NOTE-TAKER: $FILE_PATH was modified."
  echo "Did you learn something new? If yes, capture it:"
  echo "  - Unexpected errors fixed → .claude/notes/execution/{category}/{script}.md"
  echo "  - API constraints discovered → .claude/notes/directives/{category}/{directive}.md"
  echo "  - Cross-cutting patterns → .claude/notes/general.md"
  echo "See directives/subagent/note_taker.md for the full process."
fi
