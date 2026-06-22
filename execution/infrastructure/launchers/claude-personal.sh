#!/usr/bin/env bash
# claude-personal.sh -- Bash variant. Routes Claude Code through free-claude-code proxy.
# Sensitivity: public-only. NO PII / CV / leads / client data.
set -e
FCC_DIR="/c/Users/deban/dev/free-claude-code"
PORT_FILE="$FCC_DIR/.fcc-port"
[ -f "$PORT_FILE" ] || { echo "ERROR: $PORT_FILE not found." >&2; exit 1; }
PORT=$(tr -d '[:space:]' < "$PORT_FILE")
PROXY_URL="http://localhost:$PORT"

curl -fsS -m 2 "$PROXY_URL/health" > /dev/null 2>&1 || {
    echo "Proxy not responding. Start it: nohup '$USERPROFILE/.local/bin/fcc-server.exe' > '$FCC_DIR/.fcc-server.log' 2>&1 &"
    exit 1
}

export ANTHROPIC_BASE_URL="$PROXY_URL"
export ANTHROPIC_AUTH_TOKEN="freecc"

echo "PERSONAL MODE -- Claude Code -> $PROXY_URL -> GLM 5.2"
echo "Public-only. NO PII / CV / leads."
exec claude "$@"
