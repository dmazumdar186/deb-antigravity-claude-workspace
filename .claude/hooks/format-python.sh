#!/bin/bash
# format-python.sh
# PostToolUse hook: auto-formats Python files after Edit/Write.
# Receives file path as first argument ($1).

FILE_PATH="${1:-}"

# Only act on Python files
if [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi

# Skip if file doesn't exist
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# Try black first, then ruff, then skip silently
if command -v black &>/dev/null; then
  black "$FILE_PATH" --quiet 2>/dev/null || true
elif command -v ruff &>/dev/null; then
  ruff format "$FILE_PATH" --quiet 2>/dev/null || true
fi

exit 0
