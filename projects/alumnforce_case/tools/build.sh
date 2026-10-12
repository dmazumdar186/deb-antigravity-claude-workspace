#!/usr/bin/env bash
# Rebuild deck.pdf from deck.html. Run from projects/alumnforce_case/. Needs node + playwright (npm i playwright) and Chromium.
set -euo pipefail
CHROME="${CHROME:-/opt/pw-browsers/chromium-1194/chrome-linux/chrome}"
node tools/autofit.js          # per-slide zoom so no slide overflows; idempotent (strips previous bake)
"$CHROME" --headless --no-sandbox --disable-gpu --no-pdf-header-footer --virtual-time-budget=3000 \
  --print-to-pdf=deck.pdf "file://$PWD/deck.html"
node tools/measure.js | grep -c OVER && echo "WARNING: overflow remains" || echo "deck.pdf rebuilt, no overflow"
