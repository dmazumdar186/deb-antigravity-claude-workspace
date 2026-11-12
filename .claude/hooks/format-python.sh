#!/bin/bash
# format-python.sh — PostToolUse(Edit|Write) hook: auto-formats edited Python (black/ruff), edited lines only.
# Body: _post_edit.py format (reads the hook JSON on stdin; an optional $1 path overrides it).
# Picks the first Python that runs (python3 / python / py). Fails open: always exit 0.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "" >/dev/null 2>&1; then
    "$c" "$DIR/_post_edit.py" format "${1:-}"
    exit 0
  fi
done
exit 0
