#!/usr/bin/env bash
# vps_install_tools.sh - run every self-hosted tool's setup script in order on the VPS.
# Directive: directives/infrastructure/vps.md
#
# Usage:
#   bash execution/infrastructure/vps_install_tools.sh            # install/update all, write marker if all OK
#   bash execution/infrastructure/vps_install_tools.sh --dry-run  # pass --dry-run to each script, change nothing
#   bash execution/infrastructure/vps_install_tools.sh --force    # run even if the marker exists
#
# Normally started by deb-tools-install.service (User=deb). One tool failing never stops the others.
# Env overrides (tests): VPS_TOOLS_SCRIPT_DIR, DEB_TOOLS_LOG_DIR, DEB_TOOLS_MARKER, VPS_TOOLS_LIST,
# DEB_TOOLS_DOCKER_WAIT (2-second polls for the docker daemon, default 60).

set -uo pipefail

SCRIPT_DIR="${VPS_TOOLS_SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
LOG_DIR="${DEB_TOOLS_LOG_DIR:-/var/log/deb-tools}"
MARKER="${DEB_TOOLS_MARKER:-/var/lib/deb-tools/installed}"
read -r -a TOOLS <<< "${VPS_TOOLS_LIST:-freellmapi open_seo opencode voicestudio openbot pentagi}"
export DOCKER_PUBLIC_IP=127.0.0.1

DRY_RUN=0; FORCE=0; PASS=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1; PASS+=(--dry-run) ;;
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

if [ "$DRY_RUN" -eq 0 ] && [ "$FORCE" -eq 0 ] && [ -e "$MARKER" ]; then
  echo "[vps-tools] Marker $MARKER exists: already installed. Delete it (or pass --force) to re-run."
  exit 0
fi

# Logs: dry-run never writes to the real log dir; fall back to a scratch dir if not writable.
if [ "$DRY_RUN" -eq 1 ] || ! mkdir -p "$LOG_DIR" 2>/dev/null || [ ! -w "$LOG_DIR" ]; then
  LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/deb-tools.XXXXXX")"
fi

if [ "$DRY_RUN" -eq 0 ] && command -v docker >/dev/null 2>&1; then
  for _ in $(seq 1 "${DEB_TOOLS_DOCKER_WAIT:-60}"); do docker info >/dev/null 2>&1 && break; sleep 2; done
fi

declare -A RC DUR
for t in "${TOOLS[@]}"; do
  script="$SCRIPT_DIR/setup_$t.sh"
  log="$LOG_DIR/$t.log"
  echo "=== [vps-tools] $t -> $log"
  start=$(date +%s)
  if [ -f "$script" ]; then
    bash "$script" "${PASS[@]}" 2>&1 | tee "$log"
    RC[$t]=${PIPESTATUS[0]}
  else
    echo "missing $script" | tee "$log"; RC[$t]=127
  fi
  DUR[$t]=$(( $(date +%s) - start ))
done

FAILS=0; for t in "${TOOLS[@]}"; do [ "${RC[$t]}" -eq 0 ] || FAILS=$((FAILS + 1)); done
{
  printf '%-12s %-8s %6s  %s\n' TOOL RESULT SECS LOG
  for t in "${TOOLS[@]}"; do
    if [ "${RC[$t]}" -eq 0 ]; then r=OK; else r="FAIL(${RC[$t]})"; fi
    printf '%-12s %-8s %6s  %s\n' "$t" "$r" "${DUR[$t]}" "$LOG_DIR/$t.log"
  done
  printf 'finished %s  dry-run=%s  failures=%s\n' "$(date -Is)" "$DRY_RUN" "$FAILS"
} | tee "$LOG_DIR/summary.txt"

if [ "$FAILS" -gt 0 ]; then
  echo "[vps-tools] $FAILS tool(s) failed; marker NOT written. Fix, then: sudo systemctl start deb-tools-install"
  exit 1
fi
if [ "$DRY_RUN" -eq 0 ]; then
  mkdir -p "$(dirname "$MARKER")" && date -Is > "$MARKER"
  echo "[vps-tools] All tools OK; marker written: $MARKER"
fi
exit 0
