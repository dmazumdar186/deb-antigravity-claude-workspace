#!/usr/bin/env bash
# claude-glm.sh -- Launch Claude Code talking to GLM 5.2 via OpenRouter (Bash variant).
# Sensitivity guardrail: do NOT use for PII / CV / leads / AM / client data.
set -e
WORKSPACE_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
[ -f "$WORKSPACE_ROOT/.env" ] && set -a && . "$WORKSPACE_ROOT/.env" && set +a
[ -z "$OPENROUTER_API_KEY" ] && { echo "ERROR: OPENROUTER_API_KEY not set" >&2; exit 1; }
export ANTHROPIC_BASE_URL="https://openrouter.ai/api/v1"
export ANTHROPIC_AUTH_TOKEN="$OPENROUTER_API_KEY"
echo "Launching Claude Code -> OpenRouter -> z-ai/glm-5.2 (sensitivity: public-only)"
exec claude --model "z-ai/glm-5.2" "$@"
