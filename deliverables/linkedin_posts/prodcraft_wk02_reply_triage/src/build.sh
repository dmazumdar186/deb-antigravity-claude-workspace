#!/bin/sh
# One command: a ProdCraft Notes film from content.json (house style prodcraft-notes, toolkit lemo-opuscar pinned).
#   pin check → verbatim code → sound events → reading-time check → picture → score + mix → master → stems
#   → poster, drawn-text manifest, SCRIPT.md, contact sheet → black-frame check → film_eval → hashes
#   → promote the set into OUTDIR (only if every check passed).
# Writes nothing in src/ outside src/out/. Final files are built in src/out/stage.XXXXXX and moved together at the end.
# env: LEMO_OPUSCAR_HOME (the bootstrap's lemo.env sets it) or LIB = the toolkit clone at the pin
#      WS = workspace root (for the code file and film_eval.py; default: four folders up from src/)
#      OUTDIR = where the deliverables land (default: the folder above src/)
#      PLAYWRIGHT_CHROME = a headless Chromium (the toolkit's browser.mjs finds one otherwise)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LIB=${LEMO_OPUSCAR_HOME:-${LIB:-}}
[ -n "$LIB" ] || LIB=$(cd "$HERE/../.." 2>/dev/null && pwd)
[ -f "$LIB/core/render/video.mjs" ] || { echo "build.sh: set LEMO_OPUSCAR_HOME (or LIB) to the lemo-opuscar clone"; exit 1; }
export LIB LEMO_OPUSCAR_HOME="$LIB"
PIN=bebbbe1aa92a3cb4bb6f83500e61b23a17d1aa00
SHA=$(git -C "$LIB" rev-parse HEAD 2>/dev/null || echo none)
[ "$SHA" = "$PIN" ] || { echo "build.sh: toolkit is at $SHA, expected $PIN (pinned); refusing to build"; exit 1; }
WS=${WS:-$(cd "$HERE/../../../.." 2>/dev/null && pwd)}
[ -f "$WS/execution/video/film_eval.py" ] || { echo "build.sh: set WS to the workspace root"; exit 1; }
OUTDIR=${OUTDIR:-$(cd "$HERE/.." && pwd)}
PY="$LIB/.venv/bin/python"
CJ="$HERE/content.json"
NAME=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8'))['meta']['name'])" "$CJ")
SIZE=1080x1350
OUT="$HERE/out"; mkdir -p "$OUT"
for f in Newsreader-D500 Newsreader-D600 Newsreader-T400 Newsreader-T500 Newsreader-I400 JetBrainsMono-400 JetBrainsMono-700; do
  [ -f "$HERE/fonts/$f.woff2" ] || { echo "build.sh: fonts/$f.woff2 missing (run: python3 -I src/tools/fonts.py src)"; exit 1; }
done
[ -f "$HERE/assets/logo-prodcraft.png" ] || { echo "build.sh: assets/logo-prodcraft.png missing"; exit 1; }
for l in vcsl vsco2ce; do [ -d "$LIB/core/audio/instruments/$l" ] || { echo "build.sh: sample library $l missing"; exit 1; }; done
STAGE=$(mktemp -d "$OUT/stage.XXXXXX")
cd "$LIB"

"$PY" -I "$HERE/tools/code.py" "$WS" "$HERE"                                  # verbatim code → out/code.json
node core/render/events.mjs "$HERE" --size $SIZE --out "$OUT/events.json"
node core/render/readcheck.mjs "$HERE" --size $SIZE > "$OUT/readcheck.txt"    # non-zero exit stops the build
echo "readcheck ok: $(grep -c '^OK' "$OUT/readcheck.txt") texts"
node core/render/video.mjs "$HERE" --fps 30 --workers 4 --size $SIZE --out "$OUT/video.mp4"
"$PY" "$HERE/mix.py"
sh "$HERE/tools/master.sh" "$OUT/video.mp4" "$OUT/mix.wav" "$STAGE/$NAME.mp4" "$CJ"
mkdir -p "$OUT/stems"
for s in music ticks foley; do ffmpeg -y -loglevel error -i "$OUT/stems/$s.wav" -c:a aac -b:a 96k "$OUT/stems/$s.m4a"; done
node "$HERE/tools/poster.mjs" "$HERE" "$STAGE/poster.png"
node "$HERE/tools/drawn_text.mjs" "$HERE" --out "$OUT/drawn_text.json"
echo "fillText calls in film.js (must be 1, inside drawText): $(grep -c 'fillText' "$HERE/film.js")"
node "$HERE/tools/script_md.mjs" "$HERE" > "$STAGE/SCRIPT.md"
"$PY" -I "$HERE/tools/contact_sheet.py" "$STAGE/$NAME.mp4" "$CJ" "$STAGE/contact_sheet.jpg"

# gates on the staged set: black frames, then film_eval (exit 1 on any FAIL stops the build before promotion)
N=$(ffmpeg -hide_banner -nostats -i "$STAGE/$NAME.mp4" -vf blackdetect=d=0.1:pix_th=0.05 -an -f null - 2>&1 | grep -c black_start || true)
[ "$N" = "0" ] || { echo "build.sh: black frames found; nothing promoted"; exit 1; }
python3 "$WS/execution/video/film_eval.py" --video "$STAGE/$NAME.mp4" --script "$STAGE/SCRIPT.md" --facts "$OUTDIR/FACTS.md" \
  --drawn "$OUT/drawn_text.json" --profile linkedin_4x5 --out "$STAGE/EVAL_REPORT.json" --md "$STAGE/EVAL_REPORT.md"

# hashes: the MP4, three decoded frames (rgb24, BT.709 limited → full), the audio stream
{
  echo "mp4 $(sha256sum "$STAGE/$NAME.mp4" | cut -d' ' -f1)"
  for t in 0 9.6 21.0; do
    echo "frame@${t}s $(ffmpeg -loglevel error -ss $t -i "$STAGE/$NAME.mp4" -frames:v 1 -vf scale=in_color_matrix=bt709:in_range=tv:out_range=pc,format=rgb24 -f rawvideo - | sha256sum | cut -d' ' -f1)"
  done
  echo "audio(pcm) $(ffmpeg -loglevel error -i "$STAGE/$NAME.mp4" -map 0:a -f s16le - | sha256sum | cut -d' ' -f1)"
  echo "poster.png $(sha256sum "$STAGE/poster.png" | cut -d' ' -f1)"
} > "$OUT/hashes.txt"
cat "$OUT/hashes.txt"

# promote the set
for f in "$NAME.mp4" poster.png SCRIPT.md contact_sheet.jpg EVAL_REPORT.json EVAL_REPORT.md; do mv -f "$STAGE/$f" "$OUTDIR/$f"; done
rmdir "$STAGE"
rm -f "$OUT/video.mp4" "$OUT/mix.wav" "$OUT"/stems/*.wav          # scratch; the kept stems are the AAC copies (< 1 MB)
echo "done: $OUTDIR/$NAME.mp4 ($(stat -c %s "$OUTDIR/$NAME.mp4") bytes)"
