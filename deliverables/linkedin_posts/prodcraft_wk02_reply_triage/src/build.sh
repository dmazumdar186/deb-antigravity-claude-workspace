#!/bin/sh
# One command: ProdCraft weekly notes wk 02 film ("32 inboxes, 800 sends. Who replied?"), house style ProdCraft Notes.
#   pin check → fonts → verbatim code (F21) → sound events → reading-time check → picture → score + mix → master
#   (-16 LUFS, TP <= -1.5 dBTP, H.264 High, 30 fps) → poster.png → drawn-text manifest → contact sheet
# usage: sh build.sh        (the folder may sit in <clone>/films/<name>/ or anywhere else with LIB set to the pinned clone)
# env:   LIB (default: the clone two folders up, else /tmp/ext/lemo/lemo-opuscar), WS (workspace root, for reply_classifier.py),
#        PLAYWRIGHT_CHROME (a headless Chromium; the toolkit's browser.mjs finds one otherwise)
# Every deliverable is written to a temp name and moved into place only after its step succeeded.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LIB=${LIB:-$(cd "$HERE/../.." 2>/dev/null && pwd)}
[ -f "$LIB/core/render/video.mjs" ] || LIB=/tmp/ext/lemo/lemo-opuscar
export LIB
[ -f "$LIB/core/render/video.mjs" ] || { echo "build.sh: set LIB to the lemo-opuscar clone"; exit 1; }
PIN=bebbbe1aa92a3cb4bb6f83500e61b23a17d1aa00
SHA=$(git -C "$LIB" rev-parse HEAD 2>/dev/null || echo none)
[ "$SHA" = "$PIN" ] || { echo "build.sh: toolkit is at $SHA, expected $PIN (pinned); refusing to build"; exit 1; }
WS=${WS:-/home/user/deb-antigravity-claude-workspace}
SRC_PY="$WS/execution/personal_workflows/self_outbound_system/reply_classifier.py"
PY="$LIB/.venv/bin/python"
NAME=prodcraft-wk02-replies
SIZE=1080x1350
OUT="$HERE/out"; mkdir -p "$OUT"
cd "$LIB"
for l in vcsl vsco2ce; do [ -d "core/audio/instruments/$l" ] || { echo "build.sh: sample library $l missing (sh tools/fetch.sh instruments $l)"; exit 1; }; done
[ -f "$HERE/fonts/Newsreader-D500.woff2" ] || "$PY" -I "$HERE/tools/fonts.py" "$HERE"

# F21: code on screen = reply_classifier.py lines 99-107, byte-identical after a 4-space dedent
"$PY" -I "$HERE/tools/code.py" "$SRC_PY" "$HERE"

# sound events (window.EV) and the reading-time check (fails the build)
node core/render/events.mjs "$HERE" --size $SIZE
node core/render/readcheck.mjs "$HERE" --size $SIZE > "$OUT/.readcheck.tmp"
mv -f "$OUT/.readcheck.tmp" "$OUT/readcheck.txt"
echo "readcheck ok: $(grep -c '^OK' "$OUT/readcheck.txt") texts"

# picture
node core/render/video.mjs "$HERE" --fps 30 --workers 4 --size $SIZE --out "$OUT/.video.tmp.mp4"
mv -f "$OUT/.video.tmp.mp4" "$OUT/video.mp4"

# score + foley + mix, then the master (temp file + checks + atomic move inside master.sh)
"$PY" "$HERE/mix.py"
sh "$HERE/tools/master.sh" "$OUT/video.mp4" "$OUT/mix.wav" "$HERE/$NAME.mp4" 18
mkdir -p "$HERE/stems"
for s in music ticks foley; do ffmpeg -y -loglevel error -i "$OUT/stems/$s.wav" -c:a aac -b:a 96k "$HERE/stems/$s.m4a"; done
N=$(ffmpeg -hide_banner -nostats -i "$HERE/$NAME.mp4" -vf blackdetect=d=0.1:pix_th=0.05 -an -f null - 2>&1 | grep -c black_start || true)
[ "$N" = "0" ] || { echo "build.sh: black frames found"; exit 1; }

# poster (frame 0, lossless), drawn-text manifest, contact sheet
node "$HERE/tools/poster.mjs" "$HERE" "$OUT/.poster.tmp.png" && mv -f "$OUT/.poster.tmp.png" "$HERE/poster.png"
node "$HERE/tools/drawn_text.mjs" "$HERE" --out "$OUT/.drawn_text.tmp.json"
mv -f "$OUT/.drawn_text.tmp.json" "$OUT/drawn_text.json"
echo "fillText calls in film.js (must be 1, inside drawText): $(grep -c 'fillText' "$HERE/film.js")"
node "$HERE/tools/script_md.mjs" "$HERE" > "$OUT/.SCRIPT.tmp.md" && mv -f "$OUT/.SCRIPT.tmp.md" "$HERE/SCRIPT.md"
"$PY" -I "$HERE/tools/contact_sheet.py" "$HERE/$NAME.mp4" "$OUT/.contact.tmp.jpg" && mv -f "$OUT/.contact.tmp.jpg" "$HERE/contact_sheet.jpg"
echo "done: $HERE/$NAME.mp4 ($(stat -c %s "$HERE/$NAME.mp4") bytes)"
