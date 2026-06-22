# _load_env.ps1 -- dot-source helper that loads .env from the workspace root.
# Usage in a launcher script:
#   . "$PSScriptRoot\_load_env.ps1"
# After dot-sourcing, $env:OPENROUTER_API_KEY, $env:ANTHROPIC_API_KEY, etc. are set.

$workspaceRoot = (Resolve-Path "$PSScriptRoot\..\..\..").Path
$envFile = Join-Path $workspaceRoot ".env"

if (-not (Test-Path $envFile)) {
    Write-Host "WARN: .env not found at $envFile -- env vars must already be set in this shell." -ForegroundColor Yellow
    return
}

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }
    $eqIdx = $line.IndexOf("=")
    if ($eqIdx -lt 1) { return }
    $name = $line.Substring(0, $eqIdx).Trim()
    $value = $line.Substring($eqIdx + 1).Trim()
    # Strip surrounding quotes
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    Set-Item -Path "env:$name" -Value $value
}
