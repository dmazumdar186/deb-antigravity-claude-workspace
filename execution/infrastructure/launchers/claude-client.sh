#!/usr/bin/env bash
# claude-client.sh -- Bash variant. Claude Code pinned to Opus via Anthropic native.
set -e
unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN
echo "CLIENT MODE -- Claude Code -> Anthropic native -> claude-opus-4-7"
echo "PII OK. Billable."
exec claude --model "claude-opus-4-7" "$@"
