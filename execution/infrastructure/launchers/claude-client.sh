#!/usr/bin/env bash
# claude-client.sh -- Bash variant. Claude Code pinned to Fable 5.1 via Anthropic native.
set -e
unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN
echo "CLIENT MODE -- Claude Code -> Anthropic native -> claude-fable-5-1"
echo "PII OK. Billable."
exec claude --model "claude-fable-5-1" "$@"
