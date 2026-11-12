# One-time safe module reload after current worker completes.
$ErrorActionPreference='Stop'
$root='C:\Users\Dawis\ForeverRouteJarvis\DevinBridge'
$flag=Join-Path $root 'CONTINUOUS_RELOAD_PENDING.flag'
if(!(Test-Path $flag)){exit 0}
# Never clear a pause that may have been set by the owner or another task.
if(Test-Path (Join-Path $root 'PAUSED.flag')){exit 0}
$workers=@(Get-CimInstance Win32_Process|Where-Object{
 $_.Name -eq 'python.exe' -and $_.CommandLine -match 'DevinBridge.prompt_worker'})
if($workers.Count){exit 0}
$state=Get-Content (Join-Path $root 'coordinator_state.json') -Raw|ConvertFrom-Json
$active=@($state.tasks.PSObject.Properties|Where-Object{
 $_.Value.status -in @('RUNNING','DISPATCHED','VERIFYING','NEEDS_APPROVAL')})
if($active.Count){exit 0}
$name='RealJarvis ForeverRoute Scoped Autonomy'
Stop-ScheduledTask -TaskName $name
Start-Sleep -Seconds 1
# Close TOCTOU gap: a worker may start between initial check and daemon stop.
$newWorkers=@(Get-CimInstance Win32_Process|Where-Object{
 $_.Name -eq 'python.exe' -and $_.CommandLine -match 'DevinBridge.prompt_worker'})
$newState=Get-Content (Join-Path $root 'coordinator_state.json') -Raw|ConvertFrom-Json
$newActive=@($newState.tasks.PSObject.Properties|Where-Object{
 $_.Value.status -in @('RUNNING','DISPATCHED','VERIFYING','NEEDS_APPROVAL')})
if($newWorkers.Count -or $newActive.Count){
 Start-ScheduledTask -TaskName $name
 exit 0
}
Get-CimInstance Win32_Process|Where-Object{
 $_.Name -eq 'python.exe' -and $_.CommandLine -match ' -m DevinBridge.daemon'}|ForEach-Object{Stop-Process -Id $_.ProcessId -Force}
$programFile=Join-Path $root 'autonomy_scope\CDP_PROGRAM.json'
$program=Get-Content $programFile -Raw -Encoding UTF8|ConvertFrom-Json
if($program.program_id -ne 'FOREVERROUTE_CONTINUOUS_V1'){
 throw 'Unexpected program during recovery hot reload'
}
$program.max_dispatches_per_hour=12
[IO.File]::WriteAllText($programFile,($program|ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($false)))
Remove-Item $flag -Force
Start-ScheduledTask -TaskName $name
Add-Content (Join-Path $root 'continuous_autonomy_watch.log') ('reloaded recovery module '+(Get-Date -Format o))
