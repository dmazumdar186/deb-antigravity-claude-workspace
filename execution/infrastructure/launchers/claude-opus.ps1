# claude-opus.ps1 -- Claude Code session pinned to Opus (Anthropic native).
# This matches the workspace default. Exists for symmetry with the other launchers.

. "$PSScriptRoot\_load_env.ps1"

Remove-Item env:ANTHROPIC_BASE_URL -ErrorAction SilentlyContinue
Remove-Item env:ANTHROPIC_AUTH_TOKEN -ErrorAction SilentlyContinue

Write-Host "Launching Claude Code -> Anthropic native -> claude-opus-4-7" -ForegroundColor Cyan
claude --model "claude-opus-4-7" @args
