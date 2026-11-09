#!/usr/bin/env bash
# setup_opencode.sh — idempotent local install of OpenCode
# (https://github.com/anomalyco/opencode), an open-source AI coding agent CLI/TUI.
#
# Directive: directives/infrastructure/opencode.md
#
# Usage:
#   bash execution/infrastructure/setup_opencode.sh              # clone/update reference + install/upgrade CLI
#   bash execution/infrastructure/setup_opencode.sh --dry-run    # print what would run, change nothing
#   bash execution/infrastructure/setup_opencode.sh --uninstall  # remove the global CLI (clone kept)
#
# Env overrides:
#   OPENCODE_DIR      reference clone location (default: $HOME/dev/opencode)
#   OPENCODE_REF      git branch/tag/SHA for the clone (default: upstream default branch)
#   OPENCODE_VERSION  npm version/dist-tag of @opencode/cli (default: latest)
#   OPENCODE_PM       npm | bun (default: npm if present, else bun)
#   OPENCODE_SKIP_CLONE=1  install the CLI only, no source clone
#
# Install path is upstream's documented package-manager route (npm i -g @opencode/cli),
# NOT the curl|bash "YOLO" installer. Nothing from the clone is executed.
# Secrets: none written. Provider keys go via `opencode auth login` (stored by
# OpenCode in its own data dir) or env vars such as ANTHROPIC_API_KEY.

set -euo pipefail

REPO_URL="https://github.com/anomalyco/opencode.git"
PKG="@opencode/cli"
DIR="${OPENCODE_DIR:-$HOME/dev/opencode}"
REF="${OPENCODE_REF:-}"
VERSION="${OPENCODE_VERSION:-latest}"
PM="${OPENCODE_PM:-}"
SKIP_CLONE="${OPENCODE_SKIP_CLONE:-0}"
DRY_RUN=0
ACTION="up"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --uninstall|--down) ACTION="uninstall" ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '[opencode] %s\n' "$*"; }
die() { printf '[opencode] ERROR: %s\n' "$*" >&2; exit 1; }
run() {
  if [ "$DRY_RUN" -eq 1 ]; then printf '[dry-run] %s\n' "$*"; else "$@"; fi
}
have() { command -v "$1" >/dev/null 2>&1; }

# ---- package manager ----
if [ -z "$PM" ]; then
  if have npm; then PM=npm; elif have bun; then PM=bun; else PM=""; fi
fi
case "$PM" in
  npm) INSTALL=(npm install -g "$PKG@$VERSION"); REMOVE=(npm uninstall -g "$PKG") ;;
  bun) INSTALL=(bun add -g "$PKG@$VERSION"); REMOVE=(bun remove -g "$PKG") ;;
  "") die "Neither npm nor bun found. Install Node.js 20+ (or Bun), or on macOS/Linux use 'brew install anomalyco/tap/opencode-v2'." ;;
  *) die "OPENCODE_PM must be npm or bun (got '$PM')" ;;
esac

# ---- uninstall ----
if [ "$ACTION" = "uninstall" ]; then
  log "Removing global $PKG via $PM (reference clone at $DIR kept; config in ~/.config/opencode kept)"
  run "${REMOVE[@]}"
  log "Uninstalled."
  exit 0
fi

# ---- clone / update (read-only reference; never executed) ----
if [ "$SKIP_CLONE" != "1" ]; then
  have git || die "git not found. Install Git (Windows: Git for Windows / Git Bash)."
  if [ -d "$DIR/.git" ]; then
    log "Updating existing clone at $DIR"
    run git -C "$DIR" fetch --tags --prune origin
    if [ -n "$REF" ]; then
      run git -C "$DIR" checkout "$REF"
    else
      run git -C "$DIR" pull --ff-only || log "WARN: fast-forward pull failed (local changes?); keeping current checkout."
    fi
  else
    log "Cloning $REPO_URL -> $DIR (shallow)"
    run mkdir -p "$(dirname "$DIR")"
    if [ -n "$REF" ]; then
      run git clone "$REPO_URL" "$DIR"
      run git -C "$DIR" checkout "$REF"
    else
      run git clone --depth 1 "$REPO_URL" "$DIR"
    fi
  fi
fi

# ---- install / upgrade CLI ----
current=""
if have opencode; then current="$(opencode --version 2>/dev/null | head -1 || true)"; fi
if [ "$VERSION" != "latest" ] && [ -n "$current" ] && [ "${current#v}" = "${VERSION#v}" ]; then
  log "opencode $current already installed — nothing to do."
else
  log "Installing $PKG@$VERSION via $PM (current: ${current:-none}). Its postinstall fetches the platform binary from the npm registry."
  run "${INSTALL[@]}"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] opencode --version"
else
  have opencode || die "Install finished but 'opencode' is not on PATH. Add \$($PM prefix -g)/bin (npm) or ~/.bun/bin (bun) to PATH."
  log "Installed: opencode $(opencode --version 2>/dev/null | head -1)"
fi

cat <<'TXT'

OpenCode CLI ready (no service started; nothing listens on a port).
Next steps:
  1. cd into a project and run:  opencode
  2. Add a provider:  opencode auth login   (or export ANTHROPIC_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY)
  3. Headless server (optional): opencode serve  — binds 127.0.0.1 by default; keep it that way.
  4. Opt out of network extras if wanted: OPENCODE_DISABLE_AUTOUPDATE=1, OPENCODE_DISABLE_MODELS_FETCH=1,
     OPENCODE_DISABLE_FREE_MODELS=1; never use /share on client code.
  5. Remove with: bash execution/infrastructure/setup_opencode.sh --uninstall
TXT
