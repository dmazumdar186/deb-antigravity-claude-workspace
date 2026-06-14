# Remote Control launcher for this workspace.
# Spawns `claude --remote-control` in a detached PowerShell process, redirects stdout
# to a log file, tails the log for the connection URL, prints it to console.
#
# Usage (from PowerShell):
#   .\launch.ps1                    # default session name: AntiGravity-CV-Optimizer
#   .\launch.ps1 -Name "MyName"     # custom session name
#   .\launch.ps1 -Telegram          # also POST the URL to Telegram (requires env vars)
#
# Stop with: .\launch.ps1 -Stop
#
# Operator-verification status (2026-06-14): UNVERIFIED end-to-end on Windows. The
# URL-extraction regex assumes Claude CLI prints a recognizable "https://" URL on
# startup; if the CLI changes its banner, adjust the regex in $UrlPattern below.

param(
  [string]$Name = "AntiGravity-CV-Optimizer",
  [switch]$Stop,
  [switch]$Telegram
)

$LogPath = Join-Path $env:TEMP "claude-rc-$($Name -replace '[^A-Za-z0-9-]','_').log"
$PidPath = Join-Path $env:TEMP "claude-rc-$($Name -replace '[^A-Za-z0-9-]','_').pid"

function Stop-Existing {
  if (Test-Path $PidPath) {
    $oldPid = Get-Content $PidPath -ErrorAction SilentlyContinue
    if ($oldPid) {
      $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
      if ($proc -and $proc.ProcessName -eq "claude") {
        Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped prior session PID $oldPid"
      }
    }
    Remove-Item $PidPath -ErrorAction SilentlyContinue
  }
}

if ($Stop) {
  Stop-Existing
  Write-Host "Done."
  exit 0
}

Stop-Existing

Write-Host "Launching claude --remote-control `"$Name`"..."
Write-Host "  log: $LogPath"

# Clear prior log
"" | Set-Content $LogPath

$proc = Start-Process -FilePath "claude" `
  -ArgumentList "--remote-control", $Name `
  -RedirectStandardOutput $LogPath `
  -RedirectStandardError "$LogPath.err" `
  -PassThru `
  -WindowStyle Hidden

$proc.Id | Set-Content $PidPath
Write-Host "Spawned PID $($proc.Id)"

# Tail the log waiting for a URL. Up to 30s.
$UrlPattern = 'https://[^\s]+'
$found = $null
for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep -Milliseconds 500
  if (Test-Path $LogPath) {
    $content = Get-Content $LogPath -Raw -ErrorAction SilentlyContinue
    if ($content) {
      $m = [regex]::Match($content, $UrlPattern)
      if ($m.Success) {
        $found = $m.Value
        break
      }
    }
  }
  if ($proc.HasExited) {
    Write-Host "Claude process exited early. Check $LogPath and $LogPath.err"
    Get-Content $LogPath -ErrorAction SilentlyContinue | Select-Object -Last 20
    Get-Content "$LogPath.err" -ErrorAction SilentlyContinue | Select-Object -Last 20
    exit 1
  }
}

if (-not $found) {
  Write-Host "No URL found in log within 30s. Inspect $LogPath manually."
  Get-Content $LogPath -ErrorAction SilentlyContinue | Select-Object -Last 30
  exit 2
}

Write-Host ""
Write-Host "========== Remote Control URL =========="
Write-Host $found
Write-Host "========================================"
Write-Host ""
Write-Host "Open this URL on your phone browser, or scan a QR code generator linking to it."
Write-Host "To stop: .\launch.ps1 -Stop"

if ($Telegram) {
  $token = $env:TELEGRAM_BOT_TOKEN
  $chat = $env:TELEGRAM_CHAT_ID
  if (-not $token -or -not $chat) {
    Write-Host "WARN: -Telegram requested but TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID env vars missing."
  } else {
    $body = @{ chat_id = $chat; text = "Claude Remote Control ready ($Name)`n$found" } | ConvertTo-Json
    try {
      Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/sendMessage" -Method Post -ContentType "application/json" -Body $body | Out-Null
      Write-Host "Telegram notification sent."
    } catch {
      Write-Host "Telegram send failed: $_"
    }
  }
}
