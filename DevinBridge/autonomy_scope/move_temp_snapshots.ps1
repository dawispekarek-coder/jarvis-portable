$ErrorActionPreference = 'Stop'
$source = $env:TEMP
$names = @('devin_sessdb_xuku5dw2', 'devin_sessdb_sjwyt28y')
$destination = 'H:\RealJarvis\TempDevinSqliteCopies_20261110'
$original = Join-Path $env:APPDATA 'Devin\cli\sessions.db'
if (!(Test-Path -LiteralPath $original)) { throw 'Original Devin DB missing; aborting' }
$free = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='H:'").FreeSpace
if ($free -lt 17000000000) { throw 'Insufficient space on H drive' }
New-Item -ItemType Directory -Path $destination -Force | Out-Null
foreach ($name in $names) {
    $src = Join-Path $source $name
    $target = Join-Path $destination $name
    if (!(Test-Path -LiteralPath $src)) { Write-Output "ALREADY_GONE $name"; continue }
    if (Test-Path -LiteralPath $target) { Write-Output "DEST_EXISTS_NOT_OVERWRITTEN $name"; continue }
    $size = (Get-ChildItem -LiteralPath $src -File | Measure-Object Length -Sum).Sum
    Write-Output "MOVING $name BYTES=$size"
    Move-Item -LiteralPath $src -Destination $target -ErrorAction Stop
    Write-Output "MOVED $name"
}
Write-Output 'ORIGINAL_DB_PRESERVED'
