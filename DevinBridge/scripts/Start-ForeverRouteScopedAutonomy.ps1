# Dedicated bounded autonomy launcher. No legacy queue or WoW file access.
$ErrorActionPreference='Stop'
$bridge='C:\Users\Dawis\ForeverRouteJarvis\DevinBridge'
$py='C:\Users\Dawis\AppData\Local\Programs\Python\Python312\python.exe'
$root='C:\Users\Dawis\ForeverRouteJarvis'
$target=Join-Path $bridge 'autonomy_scope\workspaces\foreverroute-route-audit'
$config=Get-Content (Join-Path $bridge 'bridge_config.json') -Raw | ConvertFrom-Json
$allowed=@($config.authorized_worktrees)
if($allowed.Count -ne 1 -or $allowed[0] -ne $target){throw 'Unexpected authorized worktree; refusing startup'}
if($config.queue_root -ne (Join-Path $bridge 'autonomy_scope')){throw 'Legacy queue scope; refusing startup'}
if(!(Test-Path (Join-Path $bridge 'AUTONOMOUS_ENABLED.flag'))){throw 'Owner authorization flag missing'}
if(!(Test-Path (Join-Path $target '.git'))){throw 'Audit clone missing'}
$env:PYTHONPATH=$root
$log=Join-Path $bridge 'logs\foreverroute_scoped_autonomy.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
& $py -u -m DevinBridge.daemon *>> $log
exit $LASTEXITCODE
