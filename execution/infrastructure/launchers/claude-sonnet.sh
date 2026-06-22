#!/usr/bin/env bash
# claude-sonnet.sh -- Claude Code session pinned to Sonnet 4.6 (Anthropic native).
set -e
unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN
echo "Launching Claude Code -> Anthropic native -> claude-sonnet-4-6"
exec claude --model "claude-sonnet-4-6" "$@"
