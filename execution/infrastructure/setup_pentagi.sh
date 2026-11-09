#!/usr/bin/env bash
# setup_pentagi.sh — idempotent local install of PentAGI
# (https://github.com/vxcontrol/pentagi), a self-hosted security-testing agent.
#
# Directive: directives/infrastructure/pentagi.md
#
# AUTHORIZED TARGETS ONLY. Point PentAGI only at systems the operator owns or
# has explicit written permission to test. This script only installs and starts
# the stack on the operator's own machine; it launches no test against anything.
#
# Usage:
#   bash execution/infrastructure/setup_pentagi.sh            # install / update / start
#   bash execution/infrastructure/setup_pentagi.sh --dry-run  # print what would run
#   bash execution/infrastructure/setup_pentagi.sh --down     # stop the stack
#
# Env overrides:
#   PENTAGI_DIR      clone location (default: $HOME/dev/pentagi)
#   PENTAGI_REF      git branch/tag/SHA (default: upstream default branch)
#   HEALTH_TIMEOUT   seconds to wait for the web UI (default 240)
# LLM provider (one of):
#   OPENROUTER_API_KEY / OPENROUTER_API_TOEKN  -> custom OpenAI-compatible via OpenRouter
#   FREELLMAPI_KEY (+ optional FREELLMAPI_URL)  -> local FreeLLMAPI router
#   OPEN_AI_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY -> native provider
#
# Secrets are written only to $PENTAGI_DIR/.env (never this repo). Required
# salts/passwords that .env.example leaves at insecure defaults are replaced
# with generated random values.

set -euo pipefail

REPO_URL="https://github.com/vxcontrol/pentagi.git"
DIR="${PENTAGI_DIR:-$HOME/dev/pentagi}"
REF="${PENTAGI_REF:-}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-240}"
DRY_RUN=0
ACTION="up"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --down) ACTION="down" ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '[pentagi] %s\n' "$*"; }
die() { printf '[pentagi] ERROR: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
docker_ok() { have docker && docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; }

gen_secret() {
  if have openssl; then openssl rand -hex 32
  else od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; echo
  fi
}

# ---- down ----
if [ "$ACTION" = "down" ]; then
  [ -d "$DIR" ] || { log "Nothing to stop: $DIR does not exist."; exit 0; }
  docker_ok || die "Docker daemon not reachable; cannot stop the stack."
  log "docker compose down in $DIR (named volumes kept)"
  if [ "$DRY_RUN" -eq 1 ]; then echo "[dry-run] (cd $DIR && docker compose down)"
  else (cd "$DIR" && docker compose down); fi
  log "Stopped."
  exit 0
fi

# ---- prerequisites ----
have git || die "git not found. Install Git (Windows: Git for Windows / Git Bash / WSL)."
# A dry-run is an offline preview: don't require a live daemon just to print the plan.
if [ "$DRY_RUN" -eq 1 ]; then
  docker_ok || log "WARN: Docker daemon not reachable — a real run needs one (Docker Desktop with WSL2, or 'systemctl start docker')."
else
  docker_ok || die "Docker daemon not reachable. Start Docker Desktop (Windows/macOS: enable WSL2 backend) or 'sudo systemctl start docker' (Linux). PentAGI manages containers and needs a running daemon."
fi
log "Dir: $DIR"

# ---- clone / update ----
if [ -d "$DIR/.git" ]; then
  log "Updating existing clone"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] git -C $DIR fetch --tags --prune origin && pull --ff-only"
  else
    git -C "$DIR" fetch --tags --prune origin
    if [ -n "$REF" ]; then git -C "$DIR" checkout "$REF"
    else git -C "$DIR" pull --ff-only || log "WARN: ff pull failed; keeping current checkout."; fi
  fi
else
  log "Cloning $REPO_URL"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] mkdir -p $(dirname "$DIR") && git clone $REPO_URL $DIR"
  else
    mkdir -p "$(dirname "$DIR")"
    git clone "$REPO_URL" "$DIR"
    [ -n "$REF" ] && git -C "$DIR" checkout "$REF"
  fi
fi

# docker-compose.yml mounts these provider example files; Docker would create
# directories in their place if they are missing. Ensure they exist.
ensure_provider_file() {
  local dest="$1" src="$2"
  if [ -f "$DIR/$dest" ]; then return 0; fi
  if [ -f "$DIR/$src" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then echo "[dry-run] cp $src -> $dest"; else cp "$DIR/$src" "$DIR/$dest"; fi
  else
    if [ "$DRY_RUN" -eq 1 ]; then echo "[dry-run] touch $dest"; else : > "$DIR/$dest"; fi
  fi
}

# ---- .env ----
ENV_FILE="$DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] cp .env.example -> .env (then generate secrets + wire LLM)"
  else
    [ -f "$DIR/.env.example" ] || die ".env.example not found in clone."
    umask 077; cp "$DIR/.env.example" "$ENV_FILE"; chmod 600 "$ENV_FILE" 2>/dev/null || true
    log "Created .env from .env.example"
  fi
else
  log ".env already exists — preserving it (no secret regeneration, no LLM rewrite)."
fi

ensure_provider_file example.custom.provider.yml  examples/configs/custom-openai.provider.yml
ensure_provider_file example.ollama.provider.yml  examples/configs/ollama-llama318b.provider.yml
ensure_provider_file example.bedrock.provider.yml examples/configs/bedrock.provider.yml

# set_env KEY VALUE — set or replace a line in .env (idempotent)
set_env() {
  local key="$1" val="$2"
  [ "$DRY_RUN" -eq 1 ] && { echo "[dry-run] set $key in .env"; return 0; }
  if grep -qE "^${key}=" "$ENV_FILE"; then
    # value may contain / and &; use a non-slash delimiter and escape for sed
    local esc; esc=$(printf '%s' "$val" | sed -e 's/[\\&|]/\\&/g')
    sed -i.bak "s|^${key}=.*|${key}=${esc}|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
  else
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
}

# Replace an insecure default only if it still holds that default.
replace_default() {
  local key="$1" default="$2" newval="$3"
  [ "$DRY_RUN" -eq 1 ] && { echo "[dry-run] replace default $key if unchanged"; return 0; }
  local cur; cur=$( { grep -E "^${key}=" "$ENV_FILE" || true; } | head -1 | sed -E "s/^${key}=//; s/[[:space:]]*#.*$//")
  if [ -z "$cur" ] || [ "$cur" = "$default" ]; then set_env "$key" "$newval"; log "Generated random $key"; fi
}

# ---- secrets: replace insecure .env.example defaults ----
# The '# change this' comments on these lines are stripped by set_env's rewrite.
replace_default COOKIE_SIGNING_SALT      "salt"        "$(gen_secret)"
replace_default PENTAGI_POSTGRES_PASSWORD "postgres"   "$(gen_secret)"
replace_default NEO4J_PASSWORD           "devpassword" "$(gen_secret)"

# ---- sandbox port exposure: loopback by default (override with DOCKER_PUBLIC_IP=0.0.0.0 to expose) ----
set_env DOCKER_PUBLIC_IP "${DOCKER_PUBLIC_IP:-127.0.0.1}"

# ---- LLM provider wiring (only when .env was freshly created / still blank) ----
llm_blank() {
  [ "$DRY_RUN" -eq 1 ] && return 1
  ! grep -qE '^(OPEN_AI_KEY|ANTHROPIC_API_KEY|GEMINI_API_KEY|LLM_SERVER_KEY)=.+' "$ENV_FILE"
}
OR_KEY="${OPENROUTER_API_KEY:-${OPENROUTER_API_TOEKN:-}}"  # upstream task notes the common typo
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] wire LLM provider from env if .env has no key set"
elif llm_blank; then
  if [ -n "$OR_KEY" ]; then
    log "Wiring custom OpenAI-compatible provider -> OpenRouter"
    set_env LLM_SERVER_URL "https://openrouter.ai/api/v1"
    set_env LLM_SERVER_KEY "$OR_KEY"
    set_env LLM_SERVER_MODEL ""
    set_env LLM_SERVER_CONFIG_PATH "/opt/pentagi/conf/openrouter.provider.yml"
    set_env LLM_SERVER_PROVIDER ""
  elif [ -n "${FREELLMAPI_KEY:-}" ]; then
    FURL="${FREELLMAPI_URL:-http://host.docker.internal:3001/v1}"
    log "Wiring custom OpenAI-compatible provider -> FreeLLMAPI ($FURL)"
    set_env LLM_SERVER_URL "$FURL"
    set_env LLM_SERVER_KEY "${FREELLMAPI_KEY}"
    set_env LLM_SERVER_MODEL ""
    set_env LLM_SERVER_CONFIG_PATH "/opt/pentagi/conf/custom.provider.yml"
    set_env LLM_SERVER_PROVIDER ""
  elif [ -n "${OPEN_AI_KEY:-}" ]; then set_env OPEN_AI_KEY "$OPEN_AI_KEY"; log "Wired OPEN_AI_KEY"
  elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then set_env ANTHROPIC_API_KEY "$ANTHROPIC_API_KEY"; log "Wired ANTHROPIC_API_KEY"
  elif [ -n "${GEMINI_API_KEY:-}" ]; then set_env GEMINI_API_KEY "$GEMINI_API_KEY"; log "Wired GEMINI_API_KEY"
  else
    log "WARN: no LLM key in env (OPENROUTER_API_KEY / FREELLMAPI_KEY / OPEN_AI_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY)."
    log "WARN: stack will start but PentAGI needs at least one provider — add it to $ENV_FILE and re-run."
  fi
else
  log "LLM provider already set in .env — leaving it unchanged."
fi

# ---- start ----
log "Pulling images and starting the stack"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] (cd $DIR && docker compose pull && docker compose up -d)"
else
  (cd "$DIR" && docker compose pull) || log "WARN: pull failed; compose will build/use cached images."
  (cd "$DIR" && docker compose up -d)
fi

# ---- health (default web UI https://localhost:8443) ----
PORT="$( { grep -E '^PENTAGI_LISTEN_PORT=' "$ENV_FILE" 2>/dev/null || true; } | sed -E 's/^.*=//; s/[[:space:]].*$//')"
PORT="${PORT:-8443}"
URL="https://localhost:$PORT"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] wait up to ${HEALTH_TIMEOUT}s for $URL (self-signed TLS)"
else
  log "Waiting for the web UI at $URL (up to ${HEALTH_TIMEOUT}s; TLS is self-signed)"
  ok=0
  for _ in $(seq 1 "$HEALTH_TIMEOUT"); do
    code=$(curl -sk -o /dev/null -w '%{http_code}' "$URL/" 2>/dev/null || echo 000)
    case "$code" in 2*|3*|401|403) ok=1; break;; esac
    sleep 1
  done
  if [ "$ok" -ne 1 ]; then
    (cd "$DIR" && docker compose logs --tail 40 pentagi) || true
    die "PentAGI web UI did not respond on $URL within ${HEALTH_TIMEOUT}s."
  fi
  log "Web UI responding at $URL"
fi

cat <<EOF

PentAGI stack is up.
  Web UI:         $URL   (self-signed cert — accept the browser warning)
  Default login:  admin@pentagi.com / admin   (CHANGE THE PASSWORD on first login)
Reminders:
  * AUTHORIZED TARGETS ONLY — only systems you own or have written permission to test.
  * Flow sandboxes publish ports in the DOCKER_PORTS_BASE window (28000-29999) on
    DOCKER_PUBLIC_IP (127.0.0.1 by default); if you set it to 0.0.0.0, firewall the host.
  * Stop with: bash execution/infrastructure/setup_pentagi.sh --down
EOF
