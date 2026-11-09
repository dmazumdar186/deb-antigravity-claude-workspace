#!/usr/bin/env bash
# setup_replica_skill.sh — idempotent install of the Replica skill pack
# (https://github.com/Jakeschincariol/replica-skill): eleven Claude Code skills
# (replica-recon ... replica-deploy) that plan, rebuild, test, rebrand and ship
# a clean-room clone of an app. Pure Markdown + standard-library Python; no
# service, no ports, no API keys.
#
# Directive: directives/infrastructure/replica_skill.md
#
# Usage:
#   bash execution/infrastructure/setup_replica_skill.sh              # clone/update, scan, copy skills
#   bash execution/infrastructure/setup_replica_skill.sh --dry-run    # print the plan, change nothing
#   bash execution/infrastructure/setup_replica_skill.sh --uninstall  # print the rm commands (you run them)
#
# Env overrides:
#   REPLICA_SKILL_DIR     clone location (default: $HOME/dev/replica-skill)
#   REPLICA_SKILL_REF     git branch/tag/SHA to check out (default: upstream default branch;
#                         vetted pin: 77c9436fb3d18c3d58169efb8caf4fe906b0dc51)
#   REPLICA_SKILL_TARGET  skills dir to copy into (default: <this repo>/.claude/skills;
#                         use $HOME/.claude/skills for a user-level install)
#   REPLICA_SKILLS        space-separated subset, e.g. "replica-recon replica-entrepreneur"
#                         (default: all replica-* folders upstream ships)
#
# Security: every skill folder is scanned with `skillspector scan <dir> --no-llm -f json`
# before it is copied; HIGH/CRITICAL findings or a missing CLI abort the copy.
# Nothing upstream is executed. No secrets are read or written.

set -euo pipefail

REPO_URL="https://github.com/Jakeschincariol/replica-skill.git"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIR="${REPLICA_SKILL_DIR:-$HOME/dev/replica-skill}"
REF="${REPLICA_SKILL_REF:-}"
TARGET="${REPLICA_SKILL_TARGET:-$WORKSPACE/.claude/skills}"
SUBSET="${REPLICA_SKILLS:-}"
DRY_RUN=0
ACTION="install"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --uninstall|--down) ACTION="uninstall" ;;
    -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '[replica-skill] %s\n' "$*"; }
die() { printf '[replica-skill] ERROR: %s\n' "$*" >&2; exit 1; }
run() { if [ "$DRY_RUN" -eq 1 ]; then printf '[dry-run] %s\n' "$*"; else "$@"; fi; }
have() { command -v "$1" >/dev/null 2>&1; }

have git || die "git is required."

skill_names() {
  if [ -n "$SUBSET" ]; then
    printf '%s\n' $SUBSET
  elif [ -d "$DIR" ]; then
    (cd "$DIR" && for d in replica-*/; do [ -f "$d/SKILL.md" ] && printf '%s\n' "${d%/}"; done)
  else
    # Known set at the vetted pin (used only for a dry run before the first clone).
    printf '%s\n' replica-recon replica-architect replica-design replica-build replica-backend \
      replica-test replica-diff replica-entrepreneur replica-brand replica-launch replica-deploy
  fi
}

# ---- uninstall: print, never delete (security rule) ----
if [ "$ACTION" = uninstall ]; then
  log "Nothing is deleted automatically. To remove, run:"
  for s in $(skill_names); do
    case "$s" in replica-*) ;; *) die "refusing non replica-* name: $s" ;; esac
    [ -d "$TARGET/$s" ] && echo "  rm -rf \"$TARGET/$s\""
  done
  echo "  rm -rf \"$DIR\"   # the upstream clone"
  exit 0
fi

# ---- clone / update (fast-forward only) ----
if [ -d "$DIR/.git" ]; then
  log "Updating $DIR"
  run git -C "$DIR" fetch --tags origin
  if [ -n "$REF" ]; then
    run git -C "$DIR" checkout --quiet "$REF"
  else
    run git -C "$DIR" pull --ff-only || log "WARN: fast-forward pull failed (local changes?); keeping current checkout."
  fi
elif [ -e "$DIR" ]; then
  die "$DIR exists but is not a git clone; move it or set REPLICA_SKILL_DIR."
else
  log "Cloning $REPO_URL -> $DIR"
  run mkdir -p "$(dirname "$DIR")"
  run git clone --quiet "$REPO_URL" "$DIR"
  if [ -n "$REF" ]; then run git -C "$DIR" checkout --quiet "$REF"; fi
fi
if [ "$DRY_RUN" -eq 0 ]; then log "Upstream HEAD: $(git -C "$DIR" rev-parse HEAD)"; fi

# ---- scan + copy each skill ----
if [ "$DRY_RUN" -eq 0 ]; then
  have skillspector || die "skillspector CLI not installed; refusing to copy skills (install: uv tool install 'skillspector @ git+https://github.com/NVIDIA/skillspector.git', see directives/infrastructure/claude_plugins.md)."
fi
run mkdir -p "$TARGET"
installed=0; skipped=0
for s in $(skill_names); do
  case "$s" in replica-*) ;; *) die "refusing non replica-* name: $s" ;; esac
  SRC="$DIR/$s"; DEST="$TARGET/$s"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] skillspector scan $SRC --no-llm -f json  (abort on HIGH/CRITICAL)"
    echo "[dry-run] copy $SRC -> $DEST  (skip if identical)"
    continue
  fi
  [ -f "$SRC/SKILL.md" ] || die "$SRC/SKILL.md not found (bad REPLICA_SKILLS entry or upstream layout changed)."
  scan="$(skillspector scan "$SRC" --no-llm -f json)" || die "skillspector scan failed on $s; nothing more copied."
  if printf '%s' "$scan" | grep -qiE '"(severity|max_severity)"[[:space:]]*:[[:space:]]*"(high|critical)"'; then
    die "skillspector reported HIGH/CRITICAL findings in $s; not copied."
  fi
  if [ -d "$DEST" ] && diff -rq -x __pycache__ "$SRC" "$DEST" >/dev/null 2>&1; then
    skipped=$((skipped + 1)); continue
  fi
  mkdir -p "$DEST"
  cp -R "$SRC/." "$DEST/"
  installed=$((installed + 1))
  log "Copied $s -> $DEST (scan clean)."
done

if [ "$DRY_RUN" -eq 1 ]; then STATE="would be installed (dry-run: nothing changed)"
else STATE="installed ($installed copied, $skipped already current)"; fi
cat <<EOF

Replica skill pack $STATE.
  Skills dir: $TARGET
  Start with: /replica-recon <app URL>   (each skill writes to replica/ in your project)
  Tools need python3 3.8+, standard library only, no network.
  Remove with: bash execution/infrastructure/setup_replica_skill.sh --uninstall
EOF
