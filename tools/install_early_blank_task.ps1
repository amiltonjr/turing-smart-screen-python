# SPDX-License-Identifier: GPL-3.0-or-later
# Installs a Windows Scheduled Task to blank the Turing 3.5" screen at system startup (boot)

$taskName = "Turing Smart Screen Early Blank"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = Join-Path $scriptDir "tft_blank.exe"

# If exe doesn't exist, compile it from tft_blank.cs using standard csc.exe
if (-not (Test-Path $exePath)) {
    $csPath = Join-Path $scriptDir "tft_blank.cs"
    $csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    if (Test-Path $csc -and (Test-Path $csPath)) {
        & $csc /nologo /optimize /target:winexe /out:"$exePath" "$csPath"
    }
}

if (-not (Test-Path $exePath)) {
    Write-Error "tft_blank.exe could not be found or built at $exePath"
    exit 1
}

$action = New-ScheduledTaskAction -Execute $exePath -WorkingDirectory $scriptDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 1) -Priority 4

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User "NT AUTHORITY\SYSTEM" -RunLevel Highest -Force

Write-Host "Task '$taskName' registered successfully to run at system startup."
