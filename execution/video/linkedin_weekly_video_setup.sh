#!/usr/bin/env bash
# description: Idempotent cloud setup for the lemo-opuscar film toolkit (clone, npm, venv, CC0 sample packs, ffmpeg>=7 shim).
# Directive: directives/video/linkedin_weekly_video.md
# Usage: bash execution/video/linkedin_weekly_video_setup.sh   then: source /home/user/tools/lemo_env.sh
# Skips every step that is already done. Never runs playwright install (uses the preinstalled Chromium).
set -euo pipefail
T=/home/user/tools
L=$T/lemo-opuscar
mkdir -p "$T"

[ -d "$L/.git" ] || git clone -q https://github.com/lemomo-ai/lemo-opuscar "$L"
cd "$L"
[ -d node_modules ] || npm install --no-audit --no-fund --silent
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
[ -d core/audio/instruments/vsco2ce ] || sh tools/fetch.sh instruments vsco2ce
[ -d core/audio/instruments/vcsl ] || sh tools/fetch.sh instruments vcsl

# ffmpeg 6.1 (system) breaks mux.sh; install a static ffmpeg via imageio-ffmpeg.
if [ ! -x "$T/ffmpeg7/bin/ffmpeg" ]; then
  python3 -m venv "$T/ffmpeg7/v" && "$T/ffmpeg7/v/bin/pip" install -q imageio-ffmpeg
  mkdir -p "$T/ffmpeg7/bin"
  ln -sf "$("$T/ffmpeg7/v/bin/python" -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')" "$T/ffmpeg7/bin/ffmpeg"
fi

CHROME=$(ls -d /opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell 2>/dev/null | head -1)
cat > "$T/lemo_env.sh" <<EOF
export PATH=$T/ffmpeg7/bin:\$PATH
export PLAYWRIGHT_CHROME=$CHROME
EOF
echo "lemo-opuscar ready: $L  (source $T/lemo_env.sh)"
