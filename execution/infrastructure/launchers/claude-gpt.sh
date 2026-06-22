#!/usr/bin/env bash
# claude-gpt.sh -- Claude Code session backed by GPT-4o via OpenRouter.
set -e
WORKSPACE_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
[ -f "$WORKSPACE_ROOT/.env" ] && set -a && . "$WORKSPACE_ROOT/.env" && set +a
[ -z "$OPENROUTER_API_KEY" ] && { echo "ERROR: OPENROUTER_API_KEY not set" >&2; exit 1; }
export ANTHROPIC_BASE_URL="https://openrouter.ai/api/v1"
export ANTHROPIC_AUTH_TOKEN="$OPENROUTER_API_KEY"
echo "Launching Claude Code -> OpenRouter -> openai/gpt-4o"
exec claude --model "openai/gpt-4o" "$@"
