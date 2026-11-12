# Approval UI only. No Devin autonomous dispatch or service startup.
$root = 'C:\Users\Dawis\ForeverRouteJarvis'
$py = 'C:\Users\Dawis\AppData\Local\Programs\Python\Python312\python.exe'
$ts = 'C:\Program Files\Tailscale\tailscale.exe'
$log = Join-Path $root 'DevinBridge\approval_server_tailscale.log'
$ip = $null
for($i=0; $i -lt 36; $i++) {
  $ip = @(& $ts ip -4 2>$null | Where-Object {$_ -match '^100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]+\.[0-9]+$'}) | Select-Object -First 1
  if($ip){break}; Start-Sleep -Seconds 5
}
if(-not $ip) { Add-Content $log 'Tailscale IP unavailable; server not started'; exit 2 }
[Environment]::SetEnvironmentVariable('DEVIN_APPROVAL_HOST', $ip, 'User')
[Environment]::SetEnvironmentVariable('DEVIN_APPROVAL_BIND', $ip, 'User')
$env:DEVIN_APPROVAL_HOST = $ip
$env:DEVIN_APPROVAL_BIND = $ip
$env:PYTHONPATH = $root
while($true) {
  & $py -u -m DevinBridge.approval_server $ip 8765 2>&1 | Out-File -Append -FilePath $log
  Start-Sleep -Seconds 5
}
