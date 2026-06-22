# claude-personal.ps1 -- PERSONAL MODE: route Claude Code through the free-claude-code
# proxy at C:/Users/deban/dev/free-claude-code. The proxy maps Claude tier names (Opus/Sonnet/Haiku)
# to GLM 5.2 via OpenRouter (or whatever the proxy .env says). Cost: ~$0 per call after a small
# OR top-up; ~$1/M GLM tokens.
#
# Sensitivity: GLM is public-only. NEVER use this launcher for PII / CV content / cold-email
# leads / AM-scoped / client data. For those, use claude-client.ps1.
#
# Usage:
#   .\claude-personal.ps1                          # interactive session
#   .\claude-personal.ps1 -- "build me a 3D scene" # one-shot prompt

$FccDir = "C:\Users\deban\dev\free-claude-code"
$PortFile = Join-Path $FccDir ".fcc-port"

if (-not (Test-Path $PortFile)) {
    Write-Host "ERROR: proxy port file not found at $PortFile. Has fcc-server been installed?" -ForegroundColor Red
    Write-Host "Install: py -m uv tool install --force $FccDir" -ForegroundColor Yellow
    exit 1
}

$Port = (Get-Content $PortFile -Raw).Trim()
$ProxyUrl = "http://localhost:$Port"

# Quick health check; auto-start the proxy if down.
$health = $null
try {
    $health = Invoke-WebRequest -Uri "$ProxyUrl/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
} catch {
    Write-Host "Proxy at $ProxyUrl not responding. Starting fcc-server in background..." -ForegroundColor Yellow
    $fcc = "$env:USERPROFILE\.local\bin\fcc-server.exe"
    if (-not (Test-Path $fcc)) {
        Write-Host "ERROR: fcc-server.exe not found at $fcc" -ForegroundColor Red
        exit 1
    }
    Start-Process -FilePath $fcc -WindowStyle Hidden -WorkingDirectory $FccDir
    Start-Sleep -Seconds 6
    try {
        $health = Invoke-WebRequest -Uri "$ProxyUrl/health" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    } catch {
        Write-Host "ERROR: proxy still not healthy after auto-start. Check $FccDir\.fcc-server.log" -ForegroundColor Red
        exit 1
    }
}

# Configure Claude Code to talk to the proxy with the proxy's local auth token.
$env:ANTHROPIC_BASE_URL = $ProxyUrl
$env:ANTHROPIC_AUTH_TOKEN = "freecc"

Write-Host ""
Write-Host "PERSONAL MODE -- Claude Code -> proxy ($ProxyUrl) -> GLM 5.2 via OpenRouter" -ForegroundColor Cyan
Write-Host "Sensitivity: public-only. NO PII / CV / leads / client data." -ForegroundColor Yellow
Write-Host "If GLM is insufficient for this task, exit and use claude-client.ps1 instead." -ForegroundColor DarkGray
Write-Host ""

claude @args
