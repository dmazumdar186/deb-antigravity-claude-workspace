#!/bin/sh
# One command: Trusted Segments v2 (Archive Light Table).
#   voice → speech check → timeline + caption rules → cue check → reading-time check → two renders (burned / clean)
#   → score + mix → two masters (-16 LUFS, TP <= -1.5 dBTP) → captions → drawn-text manifest → SCRIPT.md
#   sh films/trusted-segments/build.sh          (from anywhere; LIB defaults to the clone two folders up)
# Needs: Node 20+, ffmpeg, the library's .venv (core + voice tiers), the Kokoro model and the salamander, vsco2ce and vcsl
# sample libraries (sh tools/fetch.sh voice | instruments <lib>). PLAYWRIGHT_CHROME may point to a headless Chromium.
# Every final file is written to a temp name and moved into place only when its step succeeded.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LIB=${LIB:-$(cd "$HERE/../.." && pwd)}
export LIB
[ -f "$LIB/core/render/video.mjs" ] || { echo "set LIB to the library folder"; exit 1; }
PIN=bebbbe1aa92a3cb4bb6f83500e61b23a17d1aa00
SHA=$(git -C "$LIB" rev-parse HEAD 2>/dev/null || echo none)
[ "$SHA" = "$PIN" ] || { echo "build.sh: toolkit is at $SHA, expected $PIN (pinned); refusing to build"; exit 1; }
PY="$LIB/.venv/bin/python"
cd "$LIB"
[ -f "$HERE/fonts/IBMPlexMono-400.woff2" ] || "$PY" -I "$HERE/tools/fonts.py" "$HERE"
[ -f core/tts/kokoro-v1.0.onnx ] || sh tools/fetch.sh voice
for l in salamander vsco2ce vcsl; do [ -d "core/audio/instruments/$l" ] || sh tools/fetch.sh instruments $l; done
mkdir -p "$HERE/out"

# voice: Kokoro bf_emma (offline); L16 is spoken with a tail and cut after "Segments"; speech-to-text check (small.en)
"$PY" core/tts/tts.py "$HERE/voice/lines.json" "$HERE/voice/out"
WHISPER_MODEL=small.en "$PY" -I "$HERE/tools/trim_voice.py" "$HERE/voice/lines.json" "$HERE/voice/out"
WHISPER_MODEL=small.en "$PY" core/tts/asr_check.py "$HERE/voice/lines.json" "$HERE/voice/out" --lang en

# timeline + caption rules (fails on any broken rule), cue check, reading-time check (fails the build)
node "$HERE/tools/export.mjs" "$HERE"
node "$HERE/tools/cuecheck.mjs" "$HERE"
node core/render/readcheck.mjs "$HERE" > "$HERE/out/readcheck.txt"
echo "readcheck ok: $(grep -c '^OK' "$HERE/out/readcheck.txt") texts"

# picture: with burned captions and grain-free clean master (no captions)
node core/render/video.mjs "$HERE" --fps 24 --workers 4 --out "$HERE/out/.video.tmp.mp4"
mv -f "$HERE/out/.video.tmp.mp4" "$HERE/out/video.mp4"
node core/render/video.mjs "$HERE" --fps 24 --workers 4 --q 'nosubs=1' --out "$HERE/out/.video_clean.tmp.mp4"
mv -f "$HERE/out/.video_clean.tmp.mp4" "$HERE/out/video_clean.mp4"

# score + mix, then the two masters (temp file + atomic move inside master.sh)
"$PY" "$HERE/mix.py"
sh "$HERE/tools/master.sh" "$HERE/out/video.mp4" "$HERE/out/mix.wav" "$HERE/trusted-segments.mp4" 1 26
sh "$HERE/tools/master.sh" "$HERE/out/video_clean.mp4" "$HERE/out/mix.wav" "$HERE/trusted-segments_clean.mp4" 0 23

# captions for the clean master only (a different basename, so players don't stack them on the burned file)
"$PY" core/render/srt.py "$HERE/out/cues_srt.json" "$HERE/out/.captions.tmp.srt"
mv -f "$HERE/out/.captions.tmp.srt" "$HERE/trusted-segments_clean.captions.srt"

# drawn-text manifest (every glyph run the page painted, per frame) and the script
node "$HERE/tools/drawn_text.mjs" "$HERE" --out "$HERE/out/.drawn_text.tmp.json"
mv -f "$HERE/out/.drawn_text.tmp.json" "$HERE/out/drawn_text.json"
node "$HERE/tools/script_md.mjs" "$HERE" > "$HERE/out/.SCRIPT.tmp.md" && mv -f "$HERE/out/.SCRIPT.tmp.md" "$HERE/SCRIPT.md"
echo "done: $HERE/trusted-segments.mp4 ($(du -m "$HERE/trusted-segments.mp4" | cut -f1) MB), trusted-segments_clean.mp4 ($(du -m "$HERE/trusted-segments_clean.mp4" | cut -f1) MB)"
