#!/usr/bin/env bash
# setup_voicestudio.sh — idempotent local install of VoiceStudio
# (https://github.com/debpalash/VoiceStudio), a local voice studio (TTS, voice
# cloning, transcription, dubbing) with an OpenAI-compatible API + MCP on :3900.
#
# Directive: directives/infrastructure/voicestudio.md
#
# Usage:
#   bash execution/infrastructure/setup_voicestudio.sh              # install / update / start (Docker)
#   bash execution/infrastructure/setup_voicestudio.sh --dry-run    # print what would run, change nothing
#   bash execution/infrastructure/setup_voicestudio.sh --down       # stop the stack (data volume kept)
#   bash execution/infrastructure/setup_voicestudio.sh --uninstall  # stop + print the removal commands
#   bash execution/infrastructure/setup_voicestudio.sh --with-skill # also copy upstream's `voicestudio`
#                                                                  # agent skill into .claude/skills/ (scan-gated)
#
# Env overrides:
#   VOICESTUDIO_DIR      clone location (default: $HOME/dev/voicestudio)
#   VOICESTUDIO_REF      git branch/tag/SHA to check out (default: upstream default branch;
#                        last vetted: 5aaadd51d3172fccae665bc68cf9304aa2946f98)
#   VOICESTUDIO_PROFILE  cpu | gpu | rocm (default: cpu)
#   VOICESTUDIO_IMAGE    override the container image (default: upstream compose, :stable)
#   HEALTH_TIMEOUT       seconds to wait for /health (default 600; first run pulls a large image)
#
# Secrets: OMNIVOICE_API_KEY is generated into $VOICESTUDIO_DIR/.env (mode 600),
# never into this repository. HF_TOKEN (optional, gated models) is read from your shell.

set -euo pipefail

REPO_URL="https://github.com/debpalash/VoiceStudio.git"
DIR="${VOICESTUDIO_DIR:-$HOME/dev/voicestudio}"
REF="${VOICESTUDIO_REF:-}"
PROFILE="${VOICESTUDIO_PROFILE:-cpu}"
IMAGE="${VOICESTUDIO_IMAGE:-}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-600}"
PORT=3900                       # fixed by upstream compose ("127.0.0.1:3900:3900")
PROJECT=voicestudio             # compose project → volume voicestudio_omnivoice-data
WORKSPACE="$(cd "$(dirname "$0")/../.." && pwd)"
DRY_RUN=0
ACTION="up"
WITH_SKILL=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --down) ACTION="down" ;;
    --uninstall) ACTION="uninstall" ;;
    --with-skill) WITH_SKILL=1 ;;
    -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '[voicestudio] %s\n' "$*"; }
die() { printf '[voicestudio] ERROR: %s\n' "$*" >&2; exit 1; }
run() {
  if [ "$DRY_RUN" -eq 1 ]; then printf '[dry-run] %s\n' "$*"; else "$@"; fi
}
have() { command -v "$1" >/dev/null 2>&1; }
docker_ok() { have docker && docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; }

gen_key() {
  if have openssl; then openssl rand -hex 32
  elif have python3; then python3 -I -c 'import secrets; print(secrets.token_hex(32))'
  else od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; echo
  fi
}

case "$PROFILE" in
  cpu) SERVICE=omnivoice ;;
  gpu) SERVICE=omnivoice-gpu ;;
  rocm) SERVICE=omnivoice-rocm ;;
  *) die "VOICESTUDIO_PROFILE must be cpu, gpu or rocm (got '$PROFILE')" ;;
esac

COMPOSE_FILE="$DIR/deploy/docker-compose.yml"
OVERRIDE="$DIR/.voicestudio.override.yml"   # ours, untracked; never touches upstream files
ENV_FILE="$DIR/.env"                         # upstream .gitignore covers .env

compose() {  # compose <args...> — always loopback-bound upstream file + our override
  local files=(-f "$COMPOSE_FILE")
  [ -f "$OVERRIDE" ] && files+=(-f "$OVERRIDE")
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '[dry-run] docker compose -p %s --env-file %s %s --profile %s %s\n' \
      "$PROJECT" "$ENV_FILE" "${files[*]}" "$PROFILE" "$*"
  else
    docker compose -p "$PROJECT" --env-file "$ENV_FILE" "${files[@]}" --profile "$PROFILE" "$@"
  fi
}

# ---- down / uninstall ----
if [ "$ACTION" = "down" ] || [ "$ACTION" = "uninstall" ]; then
  if [ -f "$COMPOSE_FILE" ] && { [ "$DRY_RUN" -eq 1 ] || docker_ok; }; then
    [ -f "$ENV_FILE" ] || { [ "$DRY_RUN" -eq 1 ] || { umask 077; printf 'OMNIVOICE_API_KEY=unused-for-down\n' > "$ENV_FILE"; }; }
    log "docker compose down (data volume ${PROJECT}_omnivoice-data kept)"
    compose down
  else
    log "Nothing to stop (no clone at $DIR or no Docker daemon)."
  fi
  if [ "$ACTION" = "uninstall" ]; then
    # Deliberately no automatic rm -rf (workspace security rule): print the commands instead.
    log "Stack stopped. To finish removal, run yourself:"
    log "  rm -rf \"$DIR\"                                  # clone + .env (API key)"
    log "  docker volume rm ${PROJECT}_omnivoice-data       # models + app data"
    log "  docker image rm ghcr.io/debpalash/voicestudio:stable"
  fi
  exit 0
fi

# ---- prerequisites ----
have git || die "git not found. Install Git (Windows: Git for Windows / Git Bash)."
if [ "$DRY_RUN" -eq 0 ]; then
  docker_ok || die "Docker daemon not reachable. Start Docker Desktop (Windows/macOS) or 'sudo systemctl start docker' (Linux). No-Docker path: the desktop installer from GitHub Releases (see directive)."
elif ! docker_ok; then
  log "WARN: Docker daemon not reachable here; a live run would stop at this point."
fi
log "Profile: $PROFILE ($SERVICE)   Dir: $DIR   URL: http://127.0.0.1:$PORT"

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
  log "Cloning $REPO_URL (no submodules, no install scripts run)"
  run mkdir -p "$(dirname "$DIR")"
  run git clone "$REPO_URL" "$DIR"
  if [ -n "$REF" ]; then run git -C "$DIR" checkout "$REF"; fi
fi

# ---- .env (preserved across re-runs) ----
if [ -f "$ENV_FILE" ] && grep -q '^OMNIVOICE_API_KEY=.\{16,\}' "$ENV_FILE" && ! grep -q '^OMNIVOICE_API_KEY=unused-for-down' "$ENV_FILE"; then
  log ".env exists with OMNIVOICE_API_KEY — preserving it."
else
  log "Creating $ENV_FILE with a fresh OMNIVOICE_API_KEY (mode 600)"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] write OMNIVOICE_API_KEY=<random 32-byte hex> > $ENV_FILE"
  else
    umask 077
    printf 'OMNIVOICE_API_KEY=%s\n' "$(gen_key)" > "$ENV_FILE"
    chmod 600 "$ENV_FILE" 2>/dev/null || true
  fi
fi

# ---- override: analytics hard-off (+ optional image pin) ----
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] write $OVERRIDE (services.$SERVICE: OMNIVOICE_ANALYTICS_DISABLED=1${IMAGE:+, image=$IMAGE})"
else
  {
    echo "# Written by setup_voicestudio.sh — safe to delete; regenerated each run."
    echo "services:"
    echo "  $SERVICE:"
    [ -n "$IMAGE" ] && echo "    image: $IMAGE"
    echo "    environment:"
    echo "      - OMNIVOICE_ANALYTICS_DISABLED=1"
  } > "$OVERRIDE"
fi

# ---- start ----
log "Pulling image and starting (first pull is several GB)"
compose pull "$SERVICE"
compose up -d "$SERVICE"

# ---- health ----
URL="http://127.0.0.1:$PORT"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] wait up to ${HEALTH_TIMEOUT}s for $URL/health"
else
  log "Waiting for $URL/health (up to ${HEALTH_TIMEOUT}s)"
  ok=0
  for _ in $(seq 1 "$HEALTH_TIMEOUT"); do
    if curl -fsS "$URL/health" >/dev/null 2>&1; then ok=1; break; fi
    sleep 1
  done
  if [ "$ok" -ne 1 ]; then
    compose logs --tail 40 "$SERVICE" || true
    die "VoiceStudio did not become healthy on $URL within ${HEALTH_TIMEOUT}s."
  fi
  log "Healthy."
fi

# ---- optional: agent skill (scan-gated) ----
if [ "$WITH_SKILL" -eq 1 ]; then
  SRC="$DIR/skills/voicestudio"
  DEST="$WORKSPACE/.claude/skills/voicestudio"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] skillspector scan $SRC --no-llm -f json  (abort on HIGH/CRITICAL or if CLI missing)"
    echo "[dry-run] copy $SRC -> $DEST"
  else
    have skillspector || die "skillspector CLI not installed; refusing to copy the skill (see directives/infrastructure/claude_plugins.md)."
    scan="$(skillspector scan "$SRC" --no-llm -f json)" || die "skillspector scan failed; skill not copied."
    if printf '%s' "$scan" | grep -qiE '"(severity|max_severity)"[[:space:]]*:[[:space:]]*"(high|critical)"'; then
      die "skillspector reported HIGH/CRITICAL findings; skill not copied."
    fi
    mkdir -p "$DEST"
    cp "$SRC/SKILL.md" "$DEST/SKILL.md"
    log "Skill copied to $DEST (scan clean)."
  fi
fi

[ "$DRY_RUN" -eq 1 ] && STATE="would be up (dry-run: nothing changed)" || STATE="is up"
cat <<EOF

VoiceStudio $STATE.
  Web UI:            $URL   (asks for OMNIVOICE_API_KEY: grep OMNIVOICE_API_KEY $ENV_FILE)
  OpenAI-compatible: $URL/v1/audio/speech, $URL/v1/audio/transcriptions
  MCP endpoint:      $URL/mcp
Next steps:
  1. Open the UI, enter the key, install a model (downloads from Hugging Face on your say-so).
  2. Gated models only: export HF_TOKEN=... in your shell before re-running this script.
  3. Watch first-run progress: docker compose -p $PROJECT --env-file $ENV_FILE -f $COMPOSE_FILE --profile $PROFILE logs -f
  4. Stop with: bash execution/infrastructure/setup_voicestudio.sh --down
EOF
