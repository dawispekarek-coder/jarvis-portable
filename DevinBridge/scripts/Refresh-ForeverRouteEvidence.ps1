# Evidence refresh - only in the isolated clone and when no Devin worker writes.
$ErrorActionPreference='Stop'
$bridge='C:\Users\Dawis\ForeverRouteJarvis\DevinBridge'
$work=Join-Path $bridge 'autonomy_scope\workspaces\foreverroute-route-audit'
$source=Join-Path $work 'tools\audit_56x13.py'
$csv=Join-Path $work 'tools\audit_56x13_findings.csv'
$temp=Join-Path $work 'tools\audit_56x13_findings.refresh.tmp.csv'
$backup=Join-Path $work 'tools\audit_56x13_findings.previous.csv'
$log=Join-Path $bridge 'audit_refresh.log'
$attempt=Join-Path $bridge 'audit_refresh_last_attempt.txt'
$py='C:\Users\Dawis\AppData\Local\Programs\Python\Python312\python.exe'
if(!(Test-Path (Join-Path $work '.git'))){throw 'Audit clone missing'}
if(!(Test-Path $source) -or !(Test-Path $csv)){throw 'Audit source/CSV missing'}
if(Test-Path $attempt){
 $age=((Get-Date)-(Get-Item $attempt).LastWriteTime).TotalMinutes
 if($age -lt 180){exit 0}
}
$workers=@(Get-CimInstance Win32_Process|Where-Object{
 $_.Name -eq 'python.exe' -and $_.CommandLine -match 'DevinBridge.prompt_worker'})
if($workers.Count -gt 0){exit 0}
Set-Content -LiteralPath $attempt -Value (Get-Date -Format o) -Encoding UTF8
if(Test-Path $temp){Remove-Item -LiteralPath $temp -Force}
$sourceTime=(Get-Item $source).LastWriteTimeUtc
$started=Get-Date
try{
 $proc=Start-Process -FilePath $py -ArgumentList @('-B',$source,$work,'--csv',$temp) -PassThru -WindowStyle Hidden -RedirectStandardOutput ($log+'.stdout') -RedirectStandardError ($log+'.stderr')
 if(!$proc.WaitForExit(180000)){
  try{$proc.Kill()}catch{}
  throw 'Audit timed out after 180 seconds'
 }
 if($proc.ExitCode -ne 0){throw "Audit returned $($proc.ExitCode)"}
 if(!(Test-Path $temp) -or (Get-Item $temp).Length -lt 100){throw 'Empty output'}
 if((Get-Content $temp -TotalCount 1) -ne 'proof,code,section,qid,detail'){
  throw 'Unexpected audit CSV header'
 }
 $workers=@(Get-CimInstance Win32_Process|Where-Object{
  $_.Name -eq 'python.exe' -and $_.CommandLine -match 'DevinBridge.prompt_worker'})
 if($workers.Count -gt 0 -or (Get-Item $source).LastWriteTimeUtc -ne $sourceTime){
  throw 'A worker or source change appeared during audit; discard result'
 }
 if(Test-Path $backup){Remove-Item $backup -Force}
 [IO.File]::Replace($temp,$csv,$backup,$true)
 $active=@(Get-CimInstance Win32_Process|Where-Object{
   $_.Name -eq 'python.exe' -and $_.CommandLine -match 'DevinBridge.prompt_worker'})
 if($active.Count -eq 0){
   $collector=Join-Path $bridge 'scripts\Collect-NavRegression.py'
   & $py -B $collector *> (Join-Path $bridge 'nav_test_collect.log')
 }
 Add-Content $log ((Get-Date -Format s)+' evidence refreshed, bytes='+(Get-Item $csv).Length)
}catch{
 Add-Content $log ((Get-Date -Format s)+' REFRESH SKIPPED '+$_.Exception.Message)
 if(Test-Path $temp){Remove-Item $temp -Force -ErrorAction SilentlyContinue}
}
