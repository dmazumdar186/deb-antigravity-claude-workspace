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
  CHROME="$(find /opt/pw-browsers -maxdepth 3 -type f \( -name chrome -o -name headless_shell \) 2>/dev/null | head -1)"
fi
if [ -z "${CHROME:-}" ] || [ ! -x "$CHROME" ]; then
  echo "No chromium binary found under /opt/pw-browsers" >&2
  exit 1
fi
echo "chromium: $CHROME"

# Only ever clear PNGs from a shots directory under the repo's .tmp.
case "$OUT" in
  "$ROOT"/.tmp/*) mkdir -p "$OUT"; rm -f "$OUT"/*.png ;;
  *) echo "Refusing to clear '$OUT': it is not under $ROOT/.tmp" >&2; exit 1 ;;
esac

# A build-unique token proves we are photographing OUR server and not something
# else that already had the port.
TOKEN="gaia-shots-$$-$(date +%s)"
echo "$TOKEN" > "$SITE/_shot-token.txt"
cleanup() {
  kill "$SERVER" 2>/dev/null
  rm -f "$SITE/_shot-token.txt" "$SITE/_shot-menu.html" "$SITE/_shot-outbox.html" "$SITE/_shot-stack.html"
}
trap cleanup EXIT

python3 -m http.server "$PORT" --directory "$SITE" >/dev/null 2>&1 &
SERVER=$!
READY=0
for _ in $(seq 1 40); do
  kill -0 "$SERVER" 2>/dev/null || { echo "Server exited before it was ready (port $PORT in use?)" >&2; exit 1; }
  if [ "$(curl -s --max-time 2 "http://127.0.0.1:$PORT/_shot-token.txt")" = "$TOKEN" ]; then
    READY=1; break
  fi
  sleep 0.25
done
if [ "$READY" != "1" ]; then
  echo "Could not confirm our own server on port $PORT after 10s" >&2
  exit 1
fi

FAILURES=0
shot() { # name url width height [extra flags...]
  local name="$1" url="$2" w="$3" h="$4"; shift 4
  rm -f "$OUT/$name.png"
  "$CHROME" --no-sandbox --disable-gpu --hide-scrollbars \
    --disable-dev-shm-usage --force-device-scale-factor=1 \
    --virtual-time-budget=6000 \
    --screenshot="$OUT/$name.png" --window-size="$w,$h" "$@" \
    "http://127.0.0.1:$PORT/$url" >/dev/null 2>&1
  if [ -s "$OUT/$name.png" ]; then
    echo "  $name.png  ($w x $h)"
  else
    echo "  $name.png  FAILED" >&2
    FAILURES=$((FAILURES + 1))
  fi
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

# Two interaction states that only exist after a click. A headless run cannot
# click, so each is captured from a throwaway copy of the page with a few lines
# of script appended; both copies are deleted again below.
echo "interaction states (menu open, pinned stack mid-scroll, composed message)"
python3 - "$SITE" <<'PYEOF'
import pathlib, sys
site = pathlib.Path(sys.argv[1])
src = (site / "index.html").read_text(encoding="utf-8")
menu = """<script>addEventListener('load',function(){
  setTimeout(function(){var t=document.querySelector('[data-menu-toggle]');if(t)t.click();},300);});</script>"""
outbox = """<script>addEventListener('load',function(){setTimeout(function(){
  var f=document.querySelector('[data-compose="contact-out"]');if(!f)return;
  var v={'c-first':'Aoife','c-last':'Ni Bhriain','c-email':'aoife@example.ie','c-phone':'+353 87 000 0000',
         'c-title':'Head of Environment','c-company':'Example Infrastructure','c-msg':'We need a senior ecologist for a wind farm in Co. Clare, starting January. Can we talk this week?'};
  Object.keys(v).forEach(function(k){var e=document.getElementById(k);if(e)e.value=v[k];});
  var sel=document.getElementById('c-src');if(sel)sel.value='Referral';
  f.dispatchEvent(new Event('submit',{cancelable:true,bubbles:true}));
  document.getElementById('contact-out').scrollIntoView({block:'center',behavior:'auto'});},600);});</script>"""
(site / "_shot-menu.html").write_text(src.replace("</body>", menu + "</body>"), encoding="utf-8")
hide_hero = src.replace('<section class="flow flow--pinned" data-flow',
                        '<section class="flow flow--pinned" style="display:none" data-flow')
(site / "_shot-stack.html").write_text(
    hide_hero.replace('<section class="band band--mist" id="about">',
                      '<section class="band band--mist" id="about" style="display:none">'),
    encoding="utf-8")
(site / "_shot-outbox.html").write_text(
    hide_hero.replace("</body>", outbox + "</body>")
             .replace('<section class="band band--navy" id="contact">',
                      '<section class="band band--navy" id="contact" style="padding-top:110px">'),
    encoding="utf-8")
PYEOF
shot "index-390-menu-open" "_shot-menu.html" 390 844
for pr in 0.10 0.42 0.78; do shot "index-1440-stack-$pr" "_shot-stack.html?stack=$pr" 1440 900; done
shot "index-1440-outbox"   "_shot-outbox.html" 1440 2400
echo "reduced-motion set"
shot "rm-index-1440" "index.html"      1440 9000  --force-prefers-reduced-motion
shot "rm-index-390"  "index.html"      390  15000 --force-prefers-reduced-motion
shot "rm-team-1440"  "team/index.html" 1440 2600  --force-prefers-reduced-motion
shot "rm-jobs-1440"  "jobs/index.html" 1440 2400 --force-prefers-reduced-motion

cleanup
wait "$SERVER" 2>/dev/null
echo "saved to $OUT"
ls -1 "$OUT"/*.png | wc -l
if [ "$FAILURES" -ne 0 ]; then
  echo "$FAILURES capture(s) failed" >&2
  exit 1
fi
