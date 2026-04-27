#!/bin/bash
# notify-done.sh
# Stop / Notification hook: plays a sound when Claude Code finishes a task
# or needs user input. Works on Windows (PowerShell), macOS (afplay), Linux (paplay).

if command -v powershell.exe &>/dev/null; then
  powershell.exe -NoProfile -Command "[System.Media.SystemSounds]::Asterisk.Play()" 2>/dev/null &
elif command -v afplay &>/dev/null; then
  afplay /System/Library/Sounds/Glass.aiff &
elif command -v paplay &>/dev/null; then
  paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null &
fi

exit 0
