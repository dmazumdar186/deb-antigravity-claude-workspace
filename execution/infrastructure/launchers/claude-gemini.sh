#!/usr/bin/env bash
# claude-gemini.sh -- Claude Code session backed by Gemini 2.5 Pro via OpenRouter.
set -e
WORKSPACE_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
[ -f "$WORKSPACE_ROOT/.env" ] && set -a && . "$WORKSPACE_ROOT/.env" && set +a
[ -z "$OPENROUTER_API_KEY" ] && { echo "ERROR: OPENROUTER_API_KEY not set" >&2; exit 1; }
export ANTHROPIC_BASE_URL="https://openrouter.ai/api/v1"
export ANTHROPIC_AUTH_TOKEN="$OPENROUTER_API_KEY"
echo "Launching Claude Code -> OpenRouter -> google/gemini-2.5-pro"
exec claude --model "google/gemini-2.5-pro" "$@"
