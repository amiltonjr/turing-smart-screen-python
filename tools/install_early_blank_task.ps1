# SPDX-License-Identifier: GPL-3.0-or-later
# Installs a Windows Scheduled Task to blank the Turing 3.5" screen at system startup (boot)

$taskName = "Turing Smart Screen Early Blank"
$pythonPath = (Get-Command "pythonw.exe" -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    $pythonPath = (Get-Command "python.exe" -ErrorAction SilentlyContinue).Source
}

if (-not $pythonPath) {
    Write-Error "Python executable could not be found on PATH."
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $scriptDir "tft_blank.py"

if (-not (Test-Path $scriptPath)) {
    Write-Error "tft_blank.py not found at $scriptPath"
    exit 1
}

$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`"" -WorkingDirectory $scriptDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 1) -Priority 4

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User "NT AUTHORITY\SYSTEM" -RunLevel Highest -Force

Write-Host "Task '$taskName' registered successfully to run at system startup."
