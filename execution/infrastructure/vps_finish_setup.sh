#!/usr/bin/env bash
# vps_finish_setup.sh - the one human step on the VPS (installed as /usr/local/bin/vps-finish-setup).
# Directive: directives/infrastructure/vps.md
#
# Usage (Hetzner web console, logged in as root):
#   vps-finish-setup             # Tailscale login, Claude login, trust workspace, start Remote Control, tailnet URLs
#   vps-finish-setup --dry-run   # print every action, change nothing, call no tailscale/systemctl/claude
#
# Idempotent: every step checks its own state and is skipped when already done. Safe to re-run.
# Env overrides (tests): DEB_USER (deb), DEB_HOME (/home/deb), TS_HOSTNAME (hetzner-cx43).

set -uo pipefail

U="${DEB_USER:-deb}"
H="${DEB_HOME:-/home/$U}"
WS="$H/workspace"
HOSTNAME_TS="${TS_HOSTNAME:-hetzner-cx43}"
CLAUDE="$H/.npm-global/bin/claude"
DEBPATH="$H/.npm-global/bin:$H/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
# port | target | label
SERVES=(
  "3001|http://127.0.0.1:3001|FreeLLMAPI"
  "3011|http://127.0.0.1:3011|OpenSEO"
  "3900|http://127.0.0.1:3900|VoiceStudio"
  "8443|https+insecure://127.0.0.1:8443|PentAGI"
)

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

hdr() { printf '\n==== %s ====\n' "$*"; }
dry() { printf '[dry-run] %s\n' "$*"; }
as_deb() { (cd "$H" && runuser -u "$U" -- env HOME="$H" USER="$U" NPM_CONFIG_PREFIX="$H/.npm-global" PATH="$DEBPATH" "$@"); }

if [ "$DRY_RUN" -eq 1 ]; then
  hdr "DRY RUN: nothing below is executed"
  dry "cloud-init status --wait   (wait for first-boot bootstrap)"
  hdr "1/6 Tailscale"
  dry "skip if 'tailscale status --json' BackendState=Running; else: tailscale up --ssh --hostname $HOSTNAME_TS  (open the printed URL on your phone)"
  hdr "2/6 Claude login"
  dry "skip if 'sudo -iu $U claude auth status' shows logged in; else: sudo -iu $U claude auth login  (open URL, paste code back)"
  hdr "3/6 Trust workspace"
  dry "jq: .projects[\"$WS\"].hasTrustDialogAccepted = true in $H/.claude.json (create if absent; owner $U, mode 600)"
  hdr "4/6 Remote Control"
  dry "systemctl enable --now claude-remote-control"
  hdr "5/6 Tailnet-only URLs (tailscale serve, never funnel)"
  for s in "${SERVES[@]}"; do IFS='|' read -r port target label <<< "$s"; dry "tailscale serve --bg --https=$port $target   # $label"; done
  hdr "6/6 Status"
  dry "cat /var/log/deb-tools/summary.txt; systemctl status deb-tools-install; docker ps; systemctl is-active claude-remote-control; tailscale serve status"
  exit 0
fi

[ "$(id -u)" -eq 0 ] || { echo "Run as root (log in to the Hetzner console as root), or use --dry-run." >&2; exit 1; }

hdr "0/6 Waiting for first-boot setup (cloud-init) to finish"
cloud-init status --wait >/dev/null 2>&1 || echo "WARN: cloud-init reports an error; see /var/log/deb-vps-bootstrap.log. Continuing."
for b in tailscale jq; do command -v "$b" >/dev/null || { echo "ERROR: $b is not installed; bootstrap failed. See /var/log/deb-vps-bootstrap.log" >&2; exit 1; }; done
[ -x "$CLAUDE" ] || { echo "ERROR: $CLAUDE missing; bootstrap failed. See /var/log/deb-vps-bootstrap.log" >&2; exit 1; }

# ---- 1. Tailscale ----
hdr "1/6 Tailscale"
ts_state() { tailscale status --json 2>/dev/null | jq -r '.BackendState // empty'; }
if [ "$(ts_state)" = "Running" ]; then
  echo "Already connected to your tailnet. Skipping."
else
  echo "A login URL will appear below. Open it on your phone and approve with your Tailscale account."
  tailscale up --ssh --hostname "$HOSTNAME_TS" || { echo "ERROR: tailscale up failed. Re-run vps-finish-setup." >&2; exit 1; }
fi

# ---- 2. Claude login ----
hdr "2/6 Claude Code login (user $U)"
# UNVERIFIED: assumes `claude auth status` exits 0 only when logged in, and that `claude auth login`
# runs a device/URL flow in a plain console. Fallback printed below if it does not.
if as_deb "$CLAUDE" auth status >/dev/null 2>&1; then
  echo "Already logged in. Skipping."
else
  echo "A login URL will appear. Open it on your phone, sign in, then paste the code back here."
  if ! as_deb "$CLAUDE" auth login; then
    echo "WARN: 'claude auth login' failed. Fallback: run  sudo -iu $U claude  then type /login, then re-run vps-finish-setup."
  fi
fi

# ---- 3. Pre-trust the workspace ----
hdr "3/6 Trust $WS for Claude Code"
# This is the documented "run claude in that folder once and accept the trust dialog" step, done
# non-interactively. UNVERIFIED: key name/location (projects[<path>].hasTrustDialogAccepted in ~/.claude.json).
CJ="$H/.claude.json"
if [ -f "$CJ" ] && jq -e --arg p "$WS" '.projects[$p].hasTrustDialogAccepted == true' "$CJ" >/dev/null 2>&1; then
  echo "Already trusted. Skipping."
else
  [ -s "$CJ" ] || echo '{}' > "$CJ"
  tmp="$(mktemp "$CJ.XXXXXX")"
  if jq --arg p "$WS" '.projects[$p] = ((.projects[$p] // {}) + {hasTrustDialogAccepted: true})' "$CJ" > "$tmp"; then
    mv "$tmp" "$CJ"; echo "Trusted."
  else
    rm -f "$tmp"; echo "WARN: $CJ is not valid JSON; left unchanged."
  fi
  chown "$U:$U" "$CJ"; chmod 600 "$CJ"
fi

# ---- 4. Remote Control service ----
hdr "4/6 Claude Remote Control service"
systemctl daemon-reload
systemctl enable --now claude-remote-control >/dev/null 2>&1 || true
sleep 3
if systemctl is-active --quiet claude-remote-control; then
  echo "Running. 'hetzner-cx43' should appear in the Claude app."
else
  echo "WARN: not active. If $H/.claude/.credentials.json is missing, finish step 2 and re-run."
  echo "      Logs: journalctl -u claude-remote-control -n 50"
fi

# ---- 5. Tailnet-only URLs ----
hdr "5/6 Tailnet-only URLs (tailscale serve; NOT funnel, not public)"
for s in "${SERVES[@]}"; do
  IFS='|' read -r port target label <<< "$s"
  if tailscale serve --bg --https="$port" "$target" >/dev/null 2>&1; then echo "OK   $label :$port -> $target"
  else echo "WARN $label :$port not served (enable HTTPS certificates in the Tailscale admin console, then re-run)"; fi
done

# ---- 6. Status ----
hdr "6/6 Status"
echo "-- Tool install (deb-tools-install.service): $(systemctl is-active deb-tools-install 2>/dev/null)  result=$(systemctl show -p Result --value deb-tools-install 2>/dev/null)"
if [ -f /var/lib/deb-tools/installed ]; then echo "   all tools installed ($(cat /var/lib/deb-tools/installed))"; fi
if [ -f /var/log/deb-tools/summary.txt ]; then cat /var/log/deb-tools/summary.txt
else echo "   still running (VoiceStudio images are ~17 GB). Re-run vps-finish-setup later for the table."; fi
echo "-- Containers:"; docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || echo "   docker not reachable"
echo "-- Remote Control: $(systemctl is-active claude-remote-control 2>/dev/null)"
DNS="$(tailscale status --json 2>/dev/null | jq -r '.Self.DNSName // empty' | sed 's/\.$//')"
echo "-- Tailnet URLs (open on a device signed in to the same Tailscale account):"
for s in "${SERVES[@]}"; do IFS='|' read -r port _ label <<< "$s"; echo "   $label: https://${DNS:-$HOSTNAME_TS.<tailnet>.ts.net}:$port"; done
cat <<'TXT'
-- Reminders:
   * PentAGI: scan ONLY targets you own or have written permission for (Hetzner AUP forbids the rest).
   * OpenBot: PolyForm Noncommercial licence - not for client work without a paid licence.
     Its login (email code) is done later by Claude on this box.
   * Re-run tool install: rm /var/lib/deb-tools/installed && systemctl start deb-tools-install
Done. This script is safe to re-run any time.
TXT
