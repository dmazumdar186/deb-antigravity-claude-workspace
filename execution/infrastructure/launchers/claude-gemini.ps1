# claude-gemini.ps1 -- Claude Code session backed by Gemini 2.5 Pro via OpenRouter.
# Note: native Gemini doesn't speak Anthropic protocol, but OR's adapter handles the translation.
# For free-tier Gemini direct (no OR markup), use the Python dispatcher: `py execution/modules/model_router.py gemini "..."`.

. "$PSScriptRoot\_load_env.ps1"

if (-not $env:OPENROUTER_API_KEY) {
    Write-Host "ERROR: OPENROUTER_API_KEY not set after loading .env" -ForegroundColor Red
    exit 1
}

$env:ANTHROPIC_BASE_URL = "https://openrouter.ai/api/v1"
$env:ANTHROPIC_AUTH_TOKEN = $env:OPENROUTER_API_KEY

Write-Host "Launching Claude Code -> OpenRouter -> google/gemini-2.5-pro" -ForegroundColor Cyan
claude --model "google/gemini-2.5-pro" @args
