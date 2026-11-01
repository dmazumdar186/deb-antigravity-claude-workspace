#!/bin/sh
# One command: Trusted Segments (Archive Light Table). Voice → speech check → timeline → checks → picture → score + mix → master → .srt
#   sh films/trusted-segments/build.sh
# Needs: Node 20+, ffmpeg, the library's .venv (core + voice tiers), the Kokoro model and the salamander, vsco2ce and vcsl
# sample libraries (sh tools/fetch.sh voice | instruments <lib>). PLAYWRIGHT_CHROME may point to a headless Chromium.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LIB=${LIB:-$(cd "$HERE/../.." && pwd)}
export LIB
[ -f "$LIB/core/render/video.mjs" ] || { echo "set LIB to the library folder"; exit 1; }
PY="$LIB/.venv/bin/python"
CRF=${CRF:-26}
cd "$LIB"
[ -f "$HERE/fonts/IBMPlexMono-400.woff2" ] || "$PY" -I "$HERE/tools/fonts.py" "$HERE"
[ -f core/tts/kokoro-v1.0.onnx ] || sh tools/fetch.sh voice
for l in salamander vsco2ce vcsl; do [ -d "core/audio/instruments/$l" ] || sh tools/fetch.sh instruments $l; done

# voice: Kokoro bf_emma; L16 is spoken with a tail and cut after "Segments"; speech-to-text check (small.en)
"$PY" core/tts/tts.py "$HERE/voice/lines.json" "$HERE/voice/out"
WHISPER_MODEL=small.en "$PY" -I "$HERE/tools/trim_voice.py" "$HERE/voice/lines.json" "$HERE/voice/out"
WHISPER_MODEL=small.en "$PY" core/tts/asr_check.py "$HERE/voice/lines.json" "$HERE/voice/out" --lang en
node "$HERE/tools/export.mjs" "$HERE" > /dev/null
node "$HERE/tools/cuecheck.mjs" "$HERE"
node core/render/readcheck.mjs "$HERE" > "$HERE/out/readcheck.txt" && echo "readcheck ok"

# picture, score + mix, master (two-pass loudnorm −14 LUFS, light grain, BT.709), size pass, subtitles
node core/render/video.mjs "$HERE" --fps 24 --workers 4 --out "$HERE/out/video.mp4"
"$PY" "$HERE/mix.py"
LEMO_COLOR=bt709 sh core/render/mux.sh "$HERE/out/video.mp4" "$HERE/out/mix.wav" "$HERE/out/master.mp4" 24 1
ffmpeg -y -v error -i "$HERE/out/master.mp4" -c:v libx264 -preset slow -crf "$CRF" -tune grain -pix_fmt yuv420p \
  -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -c:a copy -movflags +faststart "$HERE/trusted-segments.mp4"
"$PY" core/render/srt.py "$HERE/out/cues_srt.json" "$HERE/trusted-segments.srt"
echo "done: $HERE/trusted-segments.mp4 ($(du -m "$HERE/trusted-segments.mp4" | cut -f1) MB)"
