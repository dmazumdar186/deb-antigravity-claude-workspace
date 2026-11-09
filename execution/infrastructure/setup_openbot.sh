#!/usr/bin/env bash
# setup_openbot.sh — idempotent local install of the OpenBot headless server
# (https://github.com/nightly-labs/openbot), a local-first workspace that runs
# persistent AI agents (Claude Code, Codex, Gemini, ...) with full local access.
#
# Directive: directives/infrastructure/openbot.md
#
# LICENSE: PolyForm Noncommercial 1.0.0 (versions <= 0.1.11 were Apache-2.0).
# Commercial use (ProdCraft client work) needs a paid licence from Synthetify Labs.
#
# Usage:
#   bash execution/infrastructure/setup_openbot.sh             # clone/update + docker compose up
#   bash execution/infrastructure/setup_openbot.sh --dry-run   # print the plan, change nothing
#   bash execution/infrastructure/setup_openbot.sh --down      # stop the container (data kept)
#   bash execution/infrastructure/setup_openbot.sh --uninstall # remove container (volume kept)
#
# Env overrides:
#   OPENBOT_DIR        clone location (default: $HOME/dev/openbot)
#   OPENBOT_REF        git branch/tag/SHA to check out (default: upstream default branch;
#                      vetted: 9f69821b597eb231d4c3a026f24cc5f0a5cd333e)
#   OPENBOT_IMAGE_TAG  ghcr.io/nightly-labs/openbot tag (default: latest; e.g. 0.66.0)
#
# Uses upstream's own docker/compose.yaml + seccomp.json from the pinned clone
# (never curl|bash, never scripts/install-server.sh). The container publishes NO
# port; its Team API listens on 127.0.0.1 inside the container. No secrets are
# written: sign-in is interactive (`openbot login`, email code).

set -euo pipefail

REPO_URL="https://github.com/nightly-labs/openbot.git"
DIR="${OPENBOT_DIR:-$HOME/dev/openbot}"
REF="${OPENBOT_REF:-}"
IMAGE_TAG="${OPENBOT_IMAGE_TAG:-latest}"
IMAGE="ghcr.io/nightly-labs/openbot:${IMAGE_TAG}"
COMPOSE_DIR="$DIR/docker"
OVERRIDE="$COMPOSE_DIR/compose.override.yaml"
DRY_RUN=0
ACTION="up"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --down) ACTION="down" ;;
    --uninstall) ACTION="uninstall" ;;
    -h|--help) sed -n '2,27p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '[openbot] %s\n' "$*"; }
die() { printf '[openbot] ERROR: %s\n' "$*" >&2; exit 1; }
run() {
  if [ "$DRY_RUN" -eq 1 ]; then printf '[dry-run] %s\n' "$*"; else "$@"; fi
}
have() { command -v "$1" >/dev/null 2>&1; }
docker_ok() { have docker && docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; }
compose() {
  if [ "$DRY_RUN" -eq 1 ]; then echo "[dry-run] (cd $COMPOSE_DIR && docker compose $*)"
  else (cd "$COMPOSE_DIR" && docker compose "$@"); fi
}

# ---- down / uninstall ----
if [ "$ACTION" != "up" ]; then
  [ -f "$COMPOSE_DIR/compose.yaml" ] || { log "Nothing to stop: $COMPOSE_DIR/compose.yaml not found."; exit 0; }
  if [ "$DRY_RUN" -eq 0 ]; then docker_ok || die "Docker daemon not reachable."; fi
  if [ "$ACTION" = "down" ]; then
    log "Stopping OpenBot (container + volume kept)"
    compose stop
  else
    log "Signing out and removing the container (volume openbot-data kept)"
    if [ "$DRY_RUN" -eq 1 ]; then echo "[dry-run] (cd $COMPOSE_DIR && docker compose exec openbot openbot logout || true)"
    else (cd "$COMPOSE_DIR" && docker compose exec -T openbot openbot logout) || true; fi
    compose down
    log "Data volume kept. To delete everything: docker volume ls | grep openbot-data, then docker volume rm <name>."
  fi
  exit 0
fi

# ---- prerequisites ----
have git || die "git not found. Install Git (Windows: Git for Windows / Git Bash)."
if [ "$DRY_RUN" -eq 0 ]; then
  docker_ok || die "Docker daemon not reachable. Start Docker Desktop (Windows/macOS) or 'sudo systemctl start docker' (Linux). For the desktop app instead, download it from https://github.com/nightly-labs/openbot/releases."
elif ! docker_ok; then
  log "NOTE: Docker daemon not reachable here; a live run would stop at this point."
fi
log "Dir: $DIR   Image: $IMAGE   Ref: ${REF:-<default branch>}"

# ---- clone / update (fast-forward only) ----
if [ -d "$DIR/.git" ]; then
  log "Updating existing clone"
  run git -C "$DIR" fetch --tags --prune origin
  if [ -n "$REF" ]; then
    run git -C "$DIR" checkout "$REF"
  else
    run git -C "$DIR" pull --ff-only || log "WARN: fast-forward pull failed (local changes?); keeping current checkout."
  fi
else
  log "Cloning $REPO_URL (code is only read for compose.yaml/seccomp.json; nothing is built)"
  run mkdir -p "$(dirname "$DIR")"
  run git clone "$REPO_URL" "$DIR"
  if [ -n "$REF" ]; then run git -C "$DIR" checkout "$REF"; fi
fi
if [ "$DRY_RUN" -eq 0 ]; then
  [ -f "$COMPOSE_DIR/compose.yaml" ] && [ -f "$COMPOSE_DIR/seccomp.json" ] \
    || die "docker/compose.yaml or docker/seccomp.json missing at this ref; upstream layout changed — re-vet before continuing."
fi

# ---- image pin via override (preserved if the operator edited it) ----
# compose.override.yaml is untracked in upstream, so ff-only pulls never conflict with it.
if [ -f "$OVERRIDE" ] && ! grep -q '^# managed-by: setup_openbot.sh' "$OVERRIDE"; then
  log "$OVERRIDE exists and is operator-edited — preserving it."
else
  log "Writing $OVERRIDE (image: $IMAGE; no secrets, no published ports)"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] write $OVERRIDE -> services.openbot.image=$IMAGE"
  else
    printf '# managed-by: setup_openbot.sh (delete this line to stop the script rewriting it)\nservices:\n  openbot:\n    image: %s\n' "$IMAGE" > "$OVERRIDE"
  fi
fi

# ---- start ----
log "Pulling $IMAGE and starting the container"
compose pull openbot
compose up -d

if [ "$DRY_RUN" -eq 0 ]; then
  state="$(cd "$COMPOSE_DIR" && docker compose ps --format '{{.State}}' openbot 2>/dev/null || true)"
  [ "$state" = "running" ] || { (cd "$COMPOSE_DIR" && docker compose logs --tail 40 openbot) || true; die "OpenBot container is not running (state: ${state:-unknown})."; }
  log "Container running: $(cd "$COMPOSE_DIR" && docker compose exec -T openbot openbot version 2>/dev/null || echo '?')"
else
  echo "[dry-run] verify: docker compose ps openbot == running; docker compose exec openbot openbot version"
fi

cat <<EOF

OpenBot server container is up (publishes no port; connects out only).
Next steps:
  1. Sign in (interactive, email code — nothing is stored in this repo):
       (cd $COMPOSE_DIR && docker compose exec openbot openbot login)
  2. Use it from the desktop app, the iPhone app, or https://openbot.run/app with the same account.
     Connect a provider (Claude Code, Codex, ...) from the app; sign-ins live in the openbot-data volume.
  3. Optional: turn off product analytics in Settings > General (on by default).
  4. Stop:      bash execution/infrastructure/setup_openbot.sh --down
     Remove:    bash execution/infrastructure/setup_openbot.sh --uninstall
REMINDER: PolyForm Noncommercial — commercial/client use needs a paid licence.
EOF
