# One-shot read-only health check; Task Scheduler calls every 10 min overnight.
$ErrorActionPreference='Stop'
$root='C:\Users\Dawis\ForeverRouteJarvis'
$bridge=Join-Path $root 'DevinBridge'
$statefile=Join-Path $bridge 'night_autonomy_watch_state.json'
$log=Join-Path $bridge 'night_autonomy_watch.log'
$services=@('RealJarvis ForeverRoute Scoped Autonomy','RealJarvis DevinObserver READ ONLY','RealJarvis Devin Approvals')
$problems=New-Object System.Collections.Generic.List[string]
foreach($n in $services){
  $t=Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
  if(!$t){$problems.Add("Service missing: $n");continue}
  if($t.State -ne 'Running'){
    # Start only an already-owned installed service, never dispatch a task.
    try{Start-ScheduledTask -TaskName $n; Start-Sleep -Seconds 3
      $t=Get-ScheduledTask -TaskName $n -ErrorAction Stop}catch{}
    if($t.State -ne 'Running'){$problems.Add("Service not running: $n")}
  }
}
$dashboard=Join-Path $bridge 'dashboard_state.json'
if(!(Test-Path $dashboard)){$problems.Add('Dashboard unavailable')}
else{
  $age=((Get-Date)-(Get-Item $dashboard).LastWriteTime).TotalSeconds
  if($age -gt 300){$problems.Add("Dashboard stale: $([int]$age) seconds")}
}
if(!(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)){
  $problems.Add('Phone status/approvals port 8765 not listening')
}
$queue=Join-Path $bridge 'coordinator_state.json'
if(Test-Path $queue){
  try{
    $st=Get-Content $queue -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach($t in $st.tasks.PSObject.Properties){
      $x=$t.Value
      if($x.status -notin @('PENDING','READY')){continue}
      foreach($dep in @($x.depends_on)){
        $parent=$st.tasks.PSObject.Properties[$dep].Value
        if($parent.status -in @('FAILED','BLOCKED','NEEDS_REVIEW')){
          $r=$parent.recovery
          if($r.state -ne 'RECOVERY_DISPATCHED' -and $r.state -ne 'COOLDOWN'){
            $problems.Add("Blocked: $($t.Name) depends on $dep ($($parent.status))")
          }
        }
      }
    }
  }catch{$problems.Add('Coordinator state unreadable')}
}else{$problems.Add('Coordinator state missing')}
$names=@($problems|Sort-Object -Unique)
$sig=($names -join ' | ')
$lastSent=''
if(Test-Path $statefile){
  try{$lastSent=(Get-Content $statefile -Raw|ConvertFrom-Json).notified_signature}catch{}
}
$delivered=$false
if($sig -and $sig -ne $lastSent){
  $env:PYTHONPATH=$root
  $env:JARVIS_NIGHT_ALERT=$sig.Substring(0,[Math]::Min(850,$sig.Length))
  $py='C:\Users\Dawis\AppData\Local\Programs\Python\Python312\python.exe'
  $notify=Join-Path $bridge 'scripts\night_watch_notify.py'
  $out=@(& $py -B $notify 2>&1)
  $delivered=($LASTEXITCODE -eq 0 -and ($out -join '') -match 'NTFY_OK')
  if($delivered){$lastSent=$sig}
}
if(!$sig){$lastSent=''}
$result=[ordered]@{
  checked_at=(Get-Date).ToUniversalTime().ToString('o')
  signature=$sig
  notified_signature=$lastSent
  problems=$names
}
[System.IO.File]::WriteAllText($statefile,($result|ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false)))
Add-Content $log ('{0} {1} alert_sent={2}' -f (Get-Date -Format 's'),$(if($sig){$sig}else{'HEALTHY'}),$delivered)