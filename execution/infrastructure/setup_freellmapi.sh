#!/usr/bin/env bash
# setup_freellmapi.sh — idempotent local install of FreeLLMAPI
# (https://github.com/tashfeenahmed/freellmapi), an OpenAI-compatible router
# that stacks free-tier LLM providers behind one endpoint on :3001.
#
# Directive: directives/infrastructure/freellmapi.md
#
# Usage:
#   bash execution/infrastructure/setup_freellmapi.sh            # install / update / start
#   bash execution/infrastructure/setup_freellmapi.sh --dry-run  # print what would run
#   bash execution/infrastructure/setup_freellmapi.sh --down     # stop the stack
#
# Env overrides:
#   FREELLMAPI_DIR   clone location (default: $HOME/dev/freellmapi)
#   FREELLMAPI_REF   git branch/tag/SHA to check out (default: upstream default branch)
#   FREELLMAPI_MODE  docker | node (default: docker if a daemon is reachable, else node)
#   PORT             host port (default 3001)
#   HEALTH_TIMEOUT   seconds to wait for /api/ping (default 180)
#
# Secrets: the ENCRYPTION_KEY is generated into $FREELLMAPI_DIR/.env (mode 600),
# never into this repository. Provider keys are added in the dashboard.

set -euo pipefail

REPO_URL="https://github.com/tashfeenahmed/freellmapi.git"
DIR="${FREELLMAPI_DIR:-$HOME/dev/freellmapi}"
REF="${FREELLMAPI_REF:-}"
PORT="${PORT:-3001}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"
MODE="${FREELLMAPI_MODE:-}"
DRY_RUN=0
ACTION="up"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --down) ACTION="down" ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '[freellmapi] %s\n' "$*"; }
die() { printf '[freellmapi] ERROR: %s\n' "$*" >&2; exit 1; }
run() {
  if [ "$DRY_RUN" -eq 1 ]; then printf '[dry-run] %s\n' "$*"; else "$@"; fi
}

have() { command -v "$1" >/dev/null 2>&1; }
docker_ok() { have docker && docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; }

gen_key() {
  if have openssl; then openssl rand -hex 32
  elif have node; then node -e 'console.log(require("crypto").randomBytes(32).toString("hex"))'
  else od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; echo
  fi
}

# ---- mode ----
if [ -z "$MODE" ]; then
  if docker_ok; then MODE=docker; else MODE=node; fi
fi
case "$MODE" in docker|node) ;; *) die "FREELLMAPI_MODE must be docker or node (got '$MODE')";; esac

PIDFILE="$DIR/.freellmapi-node.pid"
LOGFILE="$DIR/.freellmapi-node.log"

# ---- down ----
if [ "$ACTION" = "down" ]; then
  [ -d "$DIR" ] || { log "Nothing to stop: $DIR does not exist."; exit 0; }
  if [ -f "$PIDFILE" ]; then
    pid="$(cat "$PIDFILE")"
    log "Stopping node process $pid"
    run kill "$pid" 2>/dev/null || true
    run rm -f "$PIDFILE"
  fi
  if docker_ok && [ -f "$DIR/docker-compose.yml" ]; then
    log "docker compose down in $DIR (data volume kept)"
    if [ "$DRY_RUN" -eq 1 ]; then echo "[dry-run] (cd $DIR && docker compose down)"
    else (cd "$DIR" && docker compose down); fi
  fi
  log "Stopped."
  exit 0
fi

# ---- prerequisites ----
have git || die "git not found. Install Git (Windows: Git for Windows / Git Bash)."
if [ "$MODE" = docker ]; then
  docker_ok || die "Docker daemon not reachable. Start Docker Desktop (Windows/macOS) or 'sudo systemctl start docker' (Linux), or set FREELLMAPI_MODE=node."
else
  have node || die "Node.js 20+ not found and Docker unavailable. Install Docker Desktop or Node 20+."
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
  [ "$node_major" -ge 20 ] || die "Node $node_major found; FreeLLMAPI needs Node 20+."
fi
log "Mode: $MODE   Dir: $DIR   Port: $PORT"

# ---- clone / update ----
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
  [ -n "$REF" ] && run git -C "$DIR" checkout "$REF"
fi

# ---- .env (preserved across re-runs) ----
if [ -f "$DIR/.env" ] && grep -q '^ENCRYPTION_KEY=.\+' "$DIR/.env"; then
  log ".env exists with ENCRYPTION_KEY — preserving it."
else
  log "Creating $DIR/.env with a fresh ENCRYPTION_KEY (mode 600)"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] write ENCRYPTION_KEY=<random 32-byte hex> PORT=$PORT > $DIR/.env"
  else
    umask 077
    printf 'ENCRYPTION_KEY=%s\nPORT=%s\n' "$(gen_key)" "$PORT" > "$DIR/.env"
    chmod 600 "$DIR/.env" 2>/dev/null || true
  fi
fi

# ---- start ----
if [ "$MODE" = docker ]; then
  log "Pulling image (falls back to local build if the pull fails)"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] (cd $DIR && PORT=$PORT docker compose pull freellmapi || docker compose build freellmapi)"
    echo "[dry-run] (cd $DIR && PORT=$PORT docker compose up -d)"
  else
    (cd "$DIR" && { PORT="$PORT" docker compose pull freellmapi || PORT="$PORT" docker compose build freellmapi; })
    (cd "$DIR" && PORT="$PORT" docker compose up -d)
  fi
else
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    log "Node server already running (pid $(cat "$PIDFILE"))."
  else
    log "npm install && npm run build (first run takes a few minutes)"
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "[dry-run] (cd $DIR && npm install && npm run build)"
      echo "[dry-run] (cd $DIR && set -a; . ./.env; NODE_ENV=production nohup node server/dist/index.js > $LOGFILE 2>&1 &)"
    else
      (cd "$DIR" && npm install && npm run build)
      (cd "$DIR" && set -a && . ./.env && set +a && NODE_ENV=production PORT="$PORT" nohup node server/dist/index.js > "$LOGFILE" 2>&1 & echo $! > "$PIDFILE")
      log "Started node server (pid $(cat "$PIDFILE")), log: $LOGFILE"
    fi
  fi
fi

# ---- health ----
URL="http://localhost:$PORT"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] wait up to ${HEALTH_TIMEOUT}s for $URL/api/ping"
else
  log "Waiting for $URL/api/ping (up to ${HEALTH_TIMEOUT}s)"
  ok=0
  for _ in $(seq 1 "$HEALTH_TIMEOUT"); do
    if curl -fsS "$URL/api/ping" >/dev/null 2>&1; then ok=1; break; fi
    sleep 1
  done
  if [ "$ok" -ne 1 ]; then
    if [ "$MODE" = docker ]; then (cd "$DIR" && docker compose logs --tail 40 freellmapi) || true
    else tail -40 "$LOGFILE" 2>/dev/null || true; fi
    die "FreeLLMAPI did not become healthy on $URL within ${HEALTH_TIMEOUT}s."
  fi
  log "Healthy: $(curl -fsS "$URL/api/ping")"
fi

cat <<EOF

FreeLLMAPI is up.
  Dashboard:        $URL
  OpenAI base URL:  $URL/v1
Next steps:
  1. Open the dashboard, add provider keys on the Keys page, reorder the Fallback Chain.
  2. Copy the unified API key from the Keys page header (keep it out of git).
  3. Point Claude Code at it:
       npx freellmapi setup-claude --url $URL --api-key <unified-key>
     or launch without touching config files:
       npx freellmapi launch
  4. Stop with: bash execution/infrastructure/setup_freellmapi.sh --down
EOF
