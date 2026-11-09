#!/usr/bin/env bash
# setup_open_seo.sh — idempotent local install of OpenSEO
# (https://github.com/every-app/open-seo), a self-hosted Semrush/Ahrefs
# alternative (keyword research, rank tracking, backlinks, site audits, MCP)
# that runs on your own DataForSEO key. Upstream path: Docker "standalone"
# stack (deploy/standalone/compose.yaml), served by Nginx on 127.0.0.1 only.
#
# Directive: directives/infrastructure/open_seo.md
#
# Usage:
#   bash execution/infrastructure/setup_open_seo.sh                  # install / update / start
#   bash execution/infrastructure/setup_open_seo.sh --dry-run        # print what would run
#   bash execution/infrastructure/setup_open_seo.sh --down           # stop (data volumes kept)
#   bash execution/infrastructure/setup_open_seo.sh --uninstall --yes  # DELETE volumes + clone
#
# Env overrides:
#   OPEN_SEO_DIR     clone location (default: $HOME/dev/open-seo)
#   OPEN_SEO_REF     git branch/tag/SHA to check out (default: upstream default branch)
#   OPEN_SEO_IMAGE   image tag (default: ghcr.io/every-app/open-seo-standalone:latest)
#   OPEN_SEO_PORT    host port for a fresh .env (default 3011; 3001 is FreeLLMAPI's)
#   HEALTH_TIMEOUT   seconds to wait for /api/health (default 240)
#
# Secrets: a random STORAGE_SECRET_KEY is generated into
# $OPEN_SEO_DIR/deploy/standalone/.env (mode 600), never into this repository.
# DATAFORSEO_API_KEY / OPENROUTER_API_KEY etc. are filled in by the operator there.

set -euo pipefail

REPO_URL="https://github.com/every-app/open-seo.git"
DIR="${OPEN_SEO_DIR:-$HOME/dev/open-seo}"
REF="${OPEN_SEO_REF:-}"
NEW_PORT="${OPEN_SEO_PORT:-3011}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-240}"
DRY_RUN=0
ACTION="up"
YES=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --down) ACTION="down" ;;
    --uninstall) ACTION="uninstall" ;;
    --yes) YES=1 ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '[open-seo] %s\n' "$*"; }
die() { printf '[open-seo] ERROR: %s\n' "$*" >&2; exit 1; }
run() {
  if [ "$DRY_RUN" -eq 1 ]; then printf '[dry-run] %s\n' "$*"; else "$@"; fi
}
have() { command -v "$1" >/dev/null 2>&1; }
docker_ok() { have docker && docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; }

gen_key() {
  if have openssl; then openssl rand -hex 32
  else od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; echo
  fi
}

STACK_DIR="$DIR/deploy/standalone"
ENV_FILE="$STACK_DIR/.env"
COMPOSE_FILE_PATH="$STACK_DIR/compose.yaml"
[ -n "${OPEN_SEO_IMAGE:-}" ] && export OPENSEO_IMAGE="$OPEN_SEO_IMAGE"

compose() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '[dry-run] docker compose -f %s --env-file %s %s\n' "$COMPOSE_FILE_PATH" "$ENV_FILE" "$*"
  else
    docker compose -f "$COMPOSE_FILE_PATH" --env-file "$ENV_FILE" "$@"
  fi
}

# ---- down / uninstall ----
if [ "$ACTION" = "down" ] || [ "$ACTION" = "uninstall" ]; then
  [ -f "$COMPOSE_FILE_PATH" ] || { log "Nothing to stop: $COMPOSE_FILE_PATH does not exist."; exit 0; }
  if [ "$ACTION" = "down" ]; then
    if [ "$DRY_RUN" -eq 1 ] || docker_ok; then compose down; else log "Docker not reachable; nothing to stop."; fi
    log "Stopped (volumes kept)."
    exit 0
  fi
  [ "$YES" -eq 1 ] || die "--uninstall deletes ALL OpenSEO data, generated secrets and $DIR. Back up first (node scripts/celld/backup.mjs backup ./backups/x), then re-run with --uninstall --yes."
  if [ "$DRY_RUN" -eq 1 ] || docker_ok; then compose down -v; fi
  run rm -rf "$DIR"
  log "Uninstalled."
  exit 0
fi

# ---- prerequisites ----
have git || die "git not found. Install Git (Windows: Git for Windows / Git Bash)."
if [ "$DRY_RUN" -eq 1 ]; then
  docker_ok || log "WARN: Docker daemon not reachable here (fine for --dry-run; live run needs Docker + Compose, >= 4 GiB RAM)."
else
  docker_ok || die "Docker daemon not reachable. Start Docker Desktop (Windows/macOS) or 'sudo systemctl start docker' (Linux). OpenSEO's self-host path is Docker-only (or Cloudflare; see directive)."
fi
log "Dir: $DIR   Ref: ${REF:-<default branch>}   Image: ${OPENSEO_IMAGE:-ghcr.io/every-app/open-seo-standalone:latest}"

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
  log "Cloning $REPO_URL"
  run mkdir -p "$(dirname "$DIR")"
  run git clone "$REPO_URL" "$DIR"
  if [ -n "$REF" ]; then run git -C "$DIR" checkout "$REF"; fi
fi

# ---- .env (preserved across re-runs) ----
if [ -f "$ENV_FILE" ] && grep -q '^STORAGE_SECRET_KEY=.\+' "$ENV_FILE" \
   && ! grep -q '^STORAGE_SECRET_KEY=replace-with' "$ENV_FILE"; then
  log ".env exists with a STORAGE_SECRET_KEY — preserving it."
else
  log "Creating $ENV_FILE from upstream .env.example with a fresh STORAGE_SECRET_KEY, PORT=$NEW_PORT (mode 600)"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] cp $STACK_DIR/.env.example $ENV_FILE; set STORAGE_SECRET_KEY=<random 32-byte hex>, PORT=$NEW_PORT, BETTER_AUTH_URL=http://localhost:$NEW_PORT"
  else
    [ -f "$STACK_DIR/.env.example" ] || die "$STACK_DIR/.env.example missing — upstream layout changed; re-read docs/SELF_HOSTING_DOCKER.md."
    umask 077
    key="$(gen_key)"
    sed -e "s|^STORAGE_SECRET_KEY=.*|STORAGE_SECRET_KEY=$key|" \
        -e "s|^PORT=.*|PORT=$NEW_PORT|" \
        -e "s|^BETTER_AUTH_URL=.*|BETTER_AUTH_URL=http://localhost:$NEW_PORT|" \
        "$STACK_DIR/.env.example" > "$ENV_FILE.tmp"
    mv "$ENV_FILE.tmp" "$ENV_FILE"
    chmod 600 "$ENV_FILE" 2>/dev/null || true
    unset key
  fi
fi

PORT_IN_USE="$NEW_PORT"
if [ -f "$ENV_FILE" ]; then
  p="$(sed -n 's/^PORT=\([0-9]\+\).*/\1/p' "$ENV_FILE" | tail -1)"; [ -n "$p" ] && PORT_IN_USE="$p"
fi
if [ -f "$ENV_FILE" ] && ! grep -q '^DATAFORSEO_API_KEY=.\+' "$ENV_FILE"; then
  log "NOTE: DATAFORSEO_API_KEY is empty — the app starts, but SEO data features stay off until you set it."
fi

# ---- start ----
log "Pulling images and starting the stack"
compose pull
compose up -d

# ---- health ----
URL="http://localhost:$PORT_IN_USE"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] wait up to ${HEALTH_TIMEOUT}s for $URL/api/health"
else
  log "Waiting for $URL/api/health (up to ${HEALTH_TIMEOUT}s)"
  ok=0
  for _ in $(seq 1 "$HEALTH_TIMEOUT"); do
    if curl -fsS "$URL/api/health" >/dev/null 2>&1; then ok=1; break; fi
    sleep 1
  done
  if [ "$ok" -ne 1 ]; then
    compose logs --tail 40 init runtime storage crawl-gateway web || true
    die "OpenSEO did not become healthy on $URL within ${HEALTH_TIMEOUT}s."
  fi
  log "Healthy."
fi

cat <<EOF

OpenSEO is up (or would be, in --dry-run).
  App:   $URL        MCP: $URL/mcp
Next steps:
  1. Open $URL and create the administrator account NOW (registration closes after the first account).
  2. Put DATAFORSEO_API_KEY (base64 of login:password) and optionally OPENROUTER_API_KEY into
     $ENV_FILE, then apply with:
       docker compose -f $COMPOSE_FILE_PATH --env-file $ENV_FILE up -d --force-recreate init web crawl-gateway
  3. MCP for Claude Code: add an HTTP MCP server at $URL/mcp (sign in, or an API key from Settings).
  4. Back up before updates: (cd $DIR && node scripts/celld/backup.mjs backup ./backups/<date>)
  5. Stop with: bash execution/infrastructure/setup_open_seo.sh --down
EOF
