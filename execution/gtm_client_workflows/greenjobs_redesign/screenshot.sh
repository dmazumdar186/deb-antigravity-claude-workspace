#!/usr/bin/env bash
# Capture the built GreenJobs demo at 390 / 768 / 1024 / 1440 for home, jobs,
# one job, insights, compass and for-keith in both editions, plus reduced-motion
# and dark-theme sets. Serves over HTTP (not file://) so fetch() and history
# behave as in production.
# Usage: bash execution/gtm_client_workflows/greenjobs_redesign/screenshot.sh [site_dir] [out_dir]
set -uo pipefail

ROOT="$(realpath -m "$(dirname "${BASH_SOURCE[0]}")/../../..")"
SITE="${1:-$ROOT/deliverables/greenjobs_redesign_2026-09-22/site}"
OUT="${2:-$ROOT/.tmp/greenjobs_redesign_shots}"
PORT="${PORT:-8741}"
PAGES="${PAGES:-index jobs job insights compass keith sectors employers}"
WIDTHS="${WIDTHS:-390 768 1024 1440}"

CHROME="/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell"
[ -x "$CHROME" ] || CHROME="$(find /opt/pw-browsers -maxdepth 3 -type f \( -name chrome -o -name headless_shell \) 2>/dev/null | head -1)"
[ -x "${CHROME:-}" ] || { echo "No chromium binary found under /opt/pw-browsers" >&2; exit 1; }

mkdir -p "$OUT"
OUT="$(realpath -m "$OUT")"
case "$OUT" in
  "$ROOT"/.tmp/*) rm -f "$OUT"/*.png ;;
  *) echo "Refusing to clear '$OUT': it is not under $ROOT/.tmp" >&2; exit 1 ;;
esac
[ -f "$SITE/index.html" ] || { echo "no built site at $SITE" >&2; exit 1; }

SERVER=""
cleanup() { kill "${SERVER:-0}" 2>/dev/null; }
trap cleanup EXIT
python3 -m http.server "$PORT" --directory "$SITE" >/dev/null 2>&1 &
SERVER=$!
READY=0
for _ in $(seq 1 40); do
  kill -0 "$SERVER" 2>/dev/null || { echo "Server exited (port $PORT in use?)" >&2; exit 1; }
  if [ "$(curl -s --max-time 2 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/ie/index.html")" = "200" ]; then READY=1; break; fi
  sleep 0.25
done
[ "$READY" = "1" ] || { echo "Could not reach our own server on port $PORT" >&2; exit 1; }

FAILURES=0
shot() { # name path width height [extra chrome flags...]
  local name="$1" path="$2" w="$3" h="$4"; shift 4
  rm -f "$OUT/$name.png"
  "$CHROME" --no-sandbox --disable-gpu --hide-scrollbars --disable-dev-shm-usage \
    --force-device-scale-factor=1 --virtual-time-budget=5000 \
    --screenshot="$OUT/$name.png" --window-size="$w,$h" "$@" "http://127.0.0.1:$PORT/$path" >/dev/null 2>&1
  if [ -s "$OUT/$name.png" ]; then echo "  $name.png ($w x $h)"; else echo "  $name.png FAILED" >&2; FAILURES=$((FAILURES + 1)); fi
}
# First job id per edition, read from the built board's dataset.
first_job() { python3 - "$SITE/$1/jobs/index.html" <<'PY'
import re, sys, json
raw = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r'id="gj-data">(.*?)</script>', raw, re.S)
print(json.loads(m.group(1))["jobs"][0]["href"] if m else "")
PY
}
url_for() { # edition page
  case "$2" in
    index) echo "$1/index.html" ;; jobs) echo "$1/jobs/index.html?view=list" ;; job) echo "$1/jobs/$(first_job "$1")" ;;
    insights) echo "$1/insights/index.html" ;; compass) echo "$1/compass/index.html" ;; keith) echo "$1/for-keith/index.html" ;;
    sectors) echo "$1/sectors/index.html" ;; employers) echo "$1/employers/index.html" ;; chooser) echo "index.html?choose" ;;
  esac
}
tall() { case "$1" in index) echo 4200 ;; jobs) echo 3200 ;; keith) echo 3600 ;; insights) echo 2360 ;; *) echo 2200 ;; esac; }

echo "viewport captures"
for ed in ie uk; do
  for page in $PAGES; do
    for w in $WIDTHS; do
      h=900; [ "$w" = 390 ] && h=844; [ "$w" = 768 ] && h=1024; [ "$w" = 1024 ] && h=768
      shot "${ed}-${page}-${w}" "$(url_for "$ed" "$page")" "$w" "$h"
    done
  done
done
shot "chooser-1440" "index.html?choose" 1440 900
shot "chooser-390" "index.html?choose" 390 844
echo "tall captures"
for page in index jobs keith insights; do
  shot "ie-${page}-1440-tall" "$(url_for ie "$page")" 1440 "$(tall "$page")"
  shot "ie-${page}-390-tall" "$(url_for ie "$page")" 390 "$(( $(tall "$page") * 3 / 2 ))"
done
shot "uk-index-1440-tall" "$(url_for uk index)" 1440 4200
echo "reduced-motion + dark"
shot "rm-ie-index-1440" "ie/index.html" 1440 4200 --force-prefers-reduced-motion
shot "rm-ie-jobs-390" "ie/jobs/index.html" 390 2400 --force-prefers-reduced-motion
shot "dark-ie-index-1440" "ie/index.html?theme=dark" 1440 4200
shot "dark-uk-jobs-1440" "uk/jobs/index.html?theme=dark" 1440 1600
shot "dark-ie-insights-390" "ie/insights/index.html?theme=dark" 390 2600
shot "dark-ie-job-768" "$(url_for ie job)?theme=dark" 768 1024
echo "state captures"
shot "ie-jobs-map-1440" "ie/jobs/index.html?view=map&theme=light" 1440 1100
shot "uk-jobs-map-390" "uk/jobs/index.html?view=map&theme=light" 390 1400
shot "ie-jobs-filtered-1440" "ie/jobs/index.html?q=engineer&sector=Water%20%26%20flood&theme=light" 1440 900
shot "ie-jobs-empty-768" "ie/jobs/index.html?q=zzzz&theme=light" 768 1024
shot "ie-compass-result-1440" "ie/compass/index.html?theme=light#a=0.0.0.5.0.2.1" 1440 1800
shot "ie-compass-result-390" "ie/compass/index.html?theme=light#a=3.1.0.5.1.2.1" 390 2200
echo "saved to $OUT"; ls -1 "$OUT"/*.png | wc -l
[ "$FAILURES" -eq 0 ] || { echo "$FAILURES capture(s) failed" >&2; exit 1; }
