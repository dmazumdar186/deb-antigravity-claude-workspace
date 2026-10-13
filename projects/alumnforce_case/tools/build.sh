#!/usr/bin/env bash
# Rebuild deck.pdf from deck.html. Run from anywhere; it changes to the project folder itself.
# Needs node with the playwright package (npm i playwright) and a Chromium binary (CHROME env or the default path).
set -euo pipefail
cd "$(dirname "$0")/.."
CHROME="${CHROME:-/opt/pw-browsers/chromium-1194/chrome-linux/chrome}"
command -v node >/dev/null || { echo "node is required" >&2; exit 1; }
[ -x "$CHROME" ] || { echo "Chromium not found at $CHROME (set CHROME=/path/to/chrome)" >&2; exit 1; }
node -e "require('playwright')" 2>/dev/null || { echo "playwright package missing: npm i playwright" >&2; exit 1; }

node tools/autofit.js          # per-slide zoom so no slide overflows; idempotent (strips previous bake)
"$CHROME" --headless --no-sandbox --disable-gpu --no-pdf-header-footer --virtual-time-budget=3000 \
  --print-to-pdf=deck.pdf "file://$PWD/deck.html"
if node tools/measure.js; then
  echo "deck.pdf rebuilt, no overflow"
else
  echo "WARNING: overflow remains or the measure step failed (exit $?)" >&2
  exit 1
fi
