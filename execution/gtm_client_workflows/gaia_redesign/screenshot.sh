#!/usr/bin/env bash
# Capture the built Gaia Talent site at three widths, plus tall full-scroll
# captures and one reduced-motion set. Serves the site over HTTP (not file://)
# so the fetches and history API behave exactly as they will in production.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SITE="${1:-$ROOT/deliverables/gaia_redesign_2026-09-17/site}"
OUT="${2:-$ROOT/.tmp/gaia_redesign_shots}"
PORT="${PORT:-8731}"

CHROME="/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell"
[ -x "$CHROME" ] || CHROME="/opt/pw-browsers/chromium"
if [ ! -x "$CHROME" ]; then
  CHROME="$(find /opt/pw-browsers -maxdepth 3 -type f -name 'chrome' -o -maxdepth 3 -type f -name 'headless_shell' 2>/dev/null | head -1)"
fi
if [ -z "${CHROME:-}" ] || [ ! -x "$CHROME" ]; then
  echo "No chromium binary found under /opt/pw-browsers" >&2
  exit 1
fi
echo "chromium: $CHROME"

mkdir -p "$OUT"
rm -f "$OUT"/*.png

python3 -m http.server "$PORT" --directory "$SITE" >/dev/null 2>&1 &
SERVER=$!
trap 'kill "$SERVER" 2>/dev/null' EXIT
for _ in $(seq 1 40); do
  curl -s -o /dev/null "http://127.0.0.1:$PORT/index.html" && break
  sleep 0.25
done

shot() { # name url width height [extra flags...]
  local name="$1" url="$2" w="$3" h="$4"; shift 4
  "$CHROME" --no-sandbox --disable-gpu --hide-scrollbars \
    --disable-dev-shm-usage --force-device-scale-factor=1 \
    --virtual-time-budget=6000 \
    --screenshot="$OUT/$name.png" --window-size="$w,$h" "$@" \
    "http://127.0.0.1:$PORT/$url" >/dev/null 2>&1
  if [ -f "$OUT/$name.png" ]; then echo "  $name.png  ($w x $h)"; else echo "  $name.png  FAILED" >&2; fi
}

echo "viewport captures"
for page in "index:index.html" "jobs:jobs/index.html" "team:team/index.html" "keith:for-keith/index.html" "404:404.html"; do
  name="${page%%:*}"; url="${page#*:}"
  shot "${name}-390"  "$url" 390 844
  shot "${name}-768"  "$url" 768 1024
  shot "${name}-1440" "$url" 1440 900
done

echo "tall full-scroll captures"
shot "index-1440-tall" "index.html"      1440 3400
shot "index-390-tall"  "index.html"      390  5200
shot "jobs-1440-tall"  "jobs/index.html" 1440 6000
shot "team-1440-tall"  "team/index.html" 1440 4000
shot "keith-1440-tall" "for-keith/index.html" 1440 6000

echo "hero scene states (headless always captures from scroll 0, so ?scene= freezes the stage)"
for n in 1 2 3 4 5 6; do shot "index-1440-flow$n" "index.html?scene=$n" 1440 900; done
shot "index-768-flow3" "index.html?scene=3" 768 1024

echo "reduced-motion set"
shot "rm-index-1440" "index.html"      1440 9000  --force-prefers-reduced-motion
shot "rm-index-390"  "index.html"      390  15000 --force-prefers-reduced-motion
shot "rm-team-1440"  "team/index.html" 1440 2600  --force-prefers-reduced-motion
shot "rm-jobs-1440"  "jobs/index.html" 1440 2400 --force-prefers-reduced-motion

kill "$SERVER" 2>/dev/null
wait "$SERVER" 2>/dev/null
echo "saved to $OUT"
ls -1 "$OUT" | wc -l
