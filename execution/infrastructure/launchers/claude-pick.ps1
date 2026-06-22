# claude-pick.ps1 -- Interactive launcher. Asks MODE first (client vs personal),
# then chains to the right launcher. Shortcut this to your desktop for
# true click-of-a-button selection.

Write-Host ""
Write-Host "Pick mode:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  [1] client    Anthropic native (Opus 4.7). Billable. PII / CV / leads OK."
Write-Host "  [2] personal  Proxy -> GLM 5.2 via OpenRouter. ~`$0 (after `$5 OR top-up). NO PII."
Write-Host ""
$modeChoice = Read-Host "Mode (1-2)"

switch ($modeChoice.Trim()) {
    "1" { & "$PSScriptRoot\claude-client.ps1" @args; return }
    "2" { & "$PSScriptRoot\claude-personal.ps1" @args; return }
    default {
        Write-Host ""
        Write-Host "Invalid mode. Falling through to the per-model picker (no mode set)." -ForegroundColor Yellow
    }
}

# --- Fallback: per-model picker (legacy behavior) ---

$models = @(
    @{Key="1"; Name="opus";    Desc="Anthropic Opus 4.7 (default, premium)"; Script="claude-opus.ps1"},
    @{Key="2"; Name="sonnet";  Desc="Anthropic Sonnet 4.6 (cheaper default)"; Script="claude-sonnet.ps1"},
    @{Key="3"; Name="glm";     Desc="GLM 5.2 via OR direct (no proxy; public-only)"; Script="claude-glm.ps1"},
    @{Key="4"; Name="gpt";     Desc="GPT-4o via OpenRouter"; Script="claude-gpt.ps1"},
    @{Key="5"; Name="gemini";  Desc="Gemini 2.5 Pro via OpenRouter"; Script="claude-gemini.ps1"}
)

Write-Host ""
Write-Host "Pick a specific model:" -ForegroundColor Cyan
Write-Host ""
foreach ($m in $models) {
    Write-Host ("  [{0}] {1,-8}  {2}" -f $m.Key, $m.Name, $m.Desc)
}
Write-Host ""
$choice = Read-Host "Choice (1-5)"

$picked = $models | Where-Object { $_.Key -eq $choice.Trim() } | Select-Object -First 1
if (-not $picked) {
    Write-Host "Invalid choice. Exiting." -ForegroundColor Red
    exit 1
}

$launcher = Join-Path $PSScriptRoot $picked.Script
& $launcher @args
