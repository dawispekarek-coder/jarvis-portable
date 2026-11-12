# Restore Windows Update active hours after the owner-approved overnight run.
$ErrorActionPreference='Stop'
$backup='C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\overnight_windows_active_hours_20261110.json'
if(!(Test-Path $backup)){exit 2}
$c=Get-Content $backup -Raw -Encoding UTF8|ConvertFrom-Json
$when=[DateTimeOffset]::Parse($c.restore_after)
if([DateTimeOffset]::Now -lt $when){exit 0}
$path=$c.reg_path
$settings=Get-ItemProperty $path
if([int]$settings.ActiveHoursStart -eq [int]$c.planned_start -and [int]$settings.ActiveHoursEnd -eq [int]$c.planned_end){
 Set-ItemProperty -Path $path -Name ActiveHoursStart -Value ([int]$c.old_start)
 Set-ItemProperty -Path $path -Name ActiveHoursEnd -Value ([int]$c.old_end)
 Add-Content 'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\night_autonomy_watch.log' ('Windows Update active hours restored at '+(Get-Date -Format s))
}
