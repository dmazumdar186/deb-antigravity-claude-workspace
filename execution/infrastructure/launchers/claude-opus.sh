#!/usr/bin/env bash
# claude-opus.sh -- Claude Code session pinned to Opus (Anthropic native).
set -e
unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN
echo "Launching Claude Code -> Anthropic native -> claude-opus-5"
exec claude --model "claude-opus-5" "$@"
