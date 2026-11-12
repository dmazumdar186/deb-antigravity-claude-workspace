#!/bin/bash
# test-touched.sh — PostToolUse(Edit|Write) hook: runs the tests that match an edited Python file.
# Picks the first Python that actually runs (python3 / python / py; skips Windows Store stubs) and
# hands stdin to test_touched.py. Fails open: no interpreter or any error -> exit 0.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "" >/dev/null 2>&1; then
    "$c" "$DIR/test_touched.py"
    exit 0
  fi
done
exit 0
