# claude-gpt.ps1 -- Claude Code session backed by GPT-4o via OpenRouter.

. "$PSScriptRoot\_load_env.ps1"

if (-not $env:OPENROUTER_API_KEY) {
    Write-Host "ERROR: OPENROUTER_API_KEY not set after loading .env" -ForegroundColor Red
    exit 1
}

$env:ANTHROPIC_BASE_URL = "https://openrouter.ai/api/v1"
$env:ANTHROPIC_AUTH_TOKEN = $env:OPENROUTER_API_KEY

Write-Host "Launching Claude Code -> OpenRouter -> openai/gpt-4o" -ForegroundColor Cyan
claude --model "openai/gpt-4o" @args
