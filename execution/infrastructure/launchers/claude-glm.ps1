# claude-glm.ps1 -- Launch Claude Code talking to GLM 5.2 via OpenRouter.
# Pattern from Nick Saraev's video (KAnDbJhNJ4E @ 7:18):
#   ANTHROPIC_BASE_URL swap + ANTHROPIC_AUTH_TOKEN = OpenRouter key.
#
# Sensitivity guardrail (per ~/.claude/rules/model-tier.md Exhibit C):
#   Do NOT use this session for PII, CV/recruiter content, cold-email leads,
#   AM-scoped data, or client data. Z.AI is China-jurisdiction.
#
# Usage (from workspace root or anywhere):
#   .\execution\infrastructure\launchers\claude-glm.ps1
#   .\execution\infrastructure\launchers\claude-glm.ps1 -- "build me a 3D nebula scene"

. "$PSScriptRoot\_load_env.ps1"

if (-not $env:OPENROUTER_API_KEY) {
    Write-Host "ERROR: OPENROUTER_API_KEY not set after loading .env" -ForegroundColor Red
    exit 1
}

$env:ANTHROPIC_BASE_URL = "https://openrouter.ai/api/v1"
$env:ANTHROPIC_AUTH_TOKEN = $env:OPENROUTER_API_KEY

Write-Host "Launching Claude Code -> OpenRouter -> z-ai/glm-5.2 (sensitivity: public-only)" -ForegroundColor Cyan
claude --model "z-ai/glm-5.2" @args
