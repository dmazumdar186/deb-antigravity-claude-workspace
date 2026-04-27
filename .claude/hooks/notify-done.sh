#!/bin/bash
# notify-done.sh
# Plays a sound notification. Accepts $1 as the sound file name (defaults to tada.wav).
# Usage: bash notify-done.sh [sound_file]
# Examples: bash notify-done.sh tada.wav
#           bash notify-done.sh notify.wav

SOUND="${1:-tada.wav}"

if command -v powershell.exe &>/dev/null; then
  powershell.exe -NoProfile -Command "(New-Object Media.SoundPlayer 'C:\Windows\Media\\$SOUND').PlaySync()" 2>/dev/null &
elif command -v afplay &>/dev/null; then
  afplay /System/Library/Sounds/Glass.aiff &
elif command -v paplay &>/dev/null; then
  paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null &
fi

exit 0
