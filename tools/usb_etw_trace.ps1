# Records Windows' USB driver trace (usbhub3, UCX, xHCI) while the pedal is
# re-enumerated, so a Code 10 / failed start can be pinned to one request.
# Needs an elevated PowerShell. Touches only the PC: restarting the device is
# the same as a replug for the pedal.
#   powershell -ExecutionPolicy Bypass -File tools\usb_etw_trace.ps1 [-InstanceId <id>]
#   ... -WaitSeconds 45   no restart: trace while the owner power-cycles / replugs the pedal
param(
    [string]$InstanceId = '',
    [int]$WaitSeconds = 0,
    [string]$Out = (Join-Path $PSScriptRoot '..\build\usb_etw')
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force $Out | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$etl = Join-Path $Out "usb_$stamp.etl"
$log = Join-Path $Out "usb_$stamp.txt"
Start-Transcript -Path $log | Out-Null

if ($WaitSeconds -le 0 -and -not $InstanceId) {
    $d = Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB\\VID_1686&PID_04A1\\' } | Select-Object -First 1
    if (-not $d) { Write-Host 'Pedal (VID_1686&PID_04A1) not present'; Stop-Transcript; exit 1 }
    $InstanceId = $d.InstanceId
}
Write-Host "device: $InstanceId"

$name = 'CFusbTrace'
logman stop $name -ets 2>$null | Out-Null
logman create trace $name -o $etl -ets -nb 128 640 -bs 128 `
    -p '{AC52AD17-CC01-4F85-8DF5-4DCE4333C99B}' 0xffffffffffffffff 0xff | Out-Host   # USB-USBHUB3
logman update trace $name -ets -p '{36DA592D-E43A-4E28-AF6F-4BC57C5A11E8}' 0xffffffffffffffff 0xff | Out-Host  # USB-UCX
logman update trace $name -ets -p '{30E1D284-5D88-459C-83FD-6345B39B19EC}' 0xffffffffffffffff 0xff | Out-Host  # USB-USBXHCI

Start-Sleep -Seconds 2
if ($WaitSeconds -gt 0) {
    Write-Host "TRACING: power-cycle or replug the pedal now ($WaitSeconds s)"
    [console]::beep(880, 300)
    Start-Sleep -Seconds $WaitSeconds
} else {
    Write-Host 'restarting device'
    pnputil /restart-device "$InstanceId" | Out-Host
    Start-Sleep -Seconds 15
}
logman stop $name -ets | Out-Host

Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like '*VID_1686*' } |
    Format-Table Status, Problem, InstanceId -AutoSize | Out-String -Width 200 | Write-Host
tracerpt $etl -o (Join-Path $Out "usb_$stamp.xml") -of XML -y | Out-Host
Write-Host "wrote $etl and usb_$stamp.xml"
Stop-Transcript | Out-Null
