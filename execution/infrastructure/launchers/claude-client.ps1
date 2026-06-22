# claude-client.ps1 -- CLIENT MODE: Claude Code with Opus 4.7 via Anthropic native.
# For billable client work, sensitive data (PII / CV / leads / client / AM), and anything
# where quality matters more than cost.
#
# Does NOT touch the free-claude-code proxy. Clears any leftover ANTHROPIC_BASE_URL.
#
# If your Anthropic balance is $0 (memory says it is as of 2026-06-22), the first call
# returns a credit-balance error. Top-up is required for client work.

. "$PSScriptRoot\_load_env.ps1"

# Remove any leftover proxy routing env vars (in case a personal-mode session leaked them).
Remove-Item env:ANTHROPIC_BASE_URL -ErrorAction SilentlyContinue
Remove-Item env:ANTHROPIC_AUTH_TOKEN -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "CLIENT MODE -- Claude Code -> Anthropic native -> claude-opus-4-7" -ForegroundColor Green
Write-Host "PII / CV / leads / client data: OK. Billable." -ForegroundColor DarkGray
Write-Host ""

claude --model "claude-opus-4-7" @args
