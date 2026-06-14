# Creates a desktop shortcut for Claude Remote Control.
# Double-clicking the shortcut opens a real cmd.exe window — provides the
# interactive tty that `claude --remote-control` needs but cannot get when
# spawned from a redirected subprocess.
#
# Usage (from any PowerShell):
#   .\install_shortcut.ps1
#
# Removes any prior shortcut with the same name and re-creates it.

param(
  [string]$SessionName = "AntiGravity-CV-Optimizer",
  [string]$ShortcutName = "Claude Remote Control"
)

$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "$ShortcutName.lnk"
$workspace = "C:\Users\deban\OneDrive\Documents\AntiGravity Project Space"

if (Test-Path $lnkPath) {
  Remove-Item $lnkPath -Force
  Write-Host "Removed prior shortcut at $lnkPath"
}

# Resolve claude.exe full path (the .ps1 wrapper plus the npm shim).
$claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claudeCmd) {
  Write-Host "ERROR: claude command not found on PATH. Install Claude Code first." -ForegroundColor Red
  exit 1
}

# We launch via cmd.exe /k so the console persists after claude exits (operator can
# read any error output without the window vanishing). cmd.exe is a real console host,
# so claude --remote-control sees a proper tty.
$cmdArgs = "/k claude --remote-control `"$SessionName`""

$wshell = New-Object -ComObject WScript.Shell
$lnk = $wshell.CreateShortcut($lnkPath)
$lnk.TargetPath = "$env:WINDIR\System32\cmd.exe"
$lnk.Arguments = $cmdArgs
$lnk.WorkingDirectory = $workspace
$lnk.IconLocation = "$env:WINDIR\System32\cmd.exe,0"
$lnk.Description = "Start Claude Remote Control session — phone connects via printed URL"
$lnk.WindowStyle = 1  # Normal window
$lnk.Save()

Write-Host "Created: $lnkPath" -ForegroundColor Green
Write-Host ""
Write-Host "How to use:"
Write-Host "  1. Double-click the 'Claude Remote Control' icon on your Desktop."
Write-Host "  2. A black console window opens — Claude prints a URL after a few seconds."
Write-Host "  3. Open that URL on your phone browser (signed into the same Anthropic account)."
Write-Host "  4. The phone now drives the laptop session — file edits, commits, deploys."
Write-Host ""
Write-Host "To stop: close the console window (this kills the remote-control session)."
