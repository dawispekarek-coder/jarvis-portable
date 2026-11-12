# Recover the precisely identified 2026-11-11 interrupted QA candidate.
# Never stop a game or modify SaveVariables. Does not clear owner-made flags.
$ErrorActionPreference='Stop'
$root='C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\live_qa'
$flag=Join-Path $root 'LIVEQA_STOP.flag'
if(!(Test-Path $flag)){exit 0}
$reason=Get-Content $flag -Raw -ErrorAction Stop
if(!$reason.StartsWith('Paused due to outstanding active candidate and WoW process; preserve game and backup. 2026-11-11')){exit 0}
if(Get-Process -Name Wow -ErrorAction SilentlyContinue){exit 0}
$manifest=Join-Path $root 'deployment.json'
if(!(Test-Path $manifest)){exit 0}
$state=Get-Content $manifest -Raw|ConvertFrom-Json
if($state.active){
 $py='C:\Users\Dawis\AppData\Local\Programs\Python\Python312\python.exe'
 $runner=Join-Path $root 'qa_manager.py'
 $result=& $py -B $runner rollback 2>&1
 if($LASTEXITCODE -ne 0){throw 'QA rollback failed: '+($result -join ' ')}
 $state=Get-Content $manifest -Raw|ConvertFrom-Json
 if($state.active -or $state.state -ne 'RESTORED'){throw 'Rollback not verified'}
}
if($state.active){exit 0}
Remove-Item $flag -Force
Start-ScheduledTask -TaskName 'RealJarvis ForeverRoute Live QA'
Add-Content (Join-Path $root 'auto_liveqa.log') ('Recovered interrupted QA after clean game exit: '+(Get-Date -Format o))