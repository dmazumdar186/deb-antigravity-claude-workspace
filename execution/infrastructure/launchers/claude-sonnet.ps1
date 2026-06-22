# claude-sonnet.ps1 -- Claude Code session pinned to Sonnet 4.6 (Anthropic native).
# Default workspace driver is Opus 4.7; this launcher pins Sonnet for the session.

. "$PSScriptRoot\_load_env.ps1"

# Native Anthropic -- clear OR override env vars if they leaked in.
Remove-Item env:ANTHROPIC_BASE_URL -ErrorAction SilentlyContinue
Remove-Item env:ANTHROPIC_AUTH_TOKEN -ErrorAction SilentlyContinue

Write-Host "Launching Claude Code -> Anthropic native -> claude-sonnet-4-6" -ForegroundColor Cyan
claude --model "claude-sonnet-4-6" @args
