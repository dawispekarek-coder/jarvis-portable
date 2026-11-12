# Windows Logon service: health check every ten minutes, no expiry.
$ErrorActionPreference='Continue'
$watch='C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\scripts\Continuous-Development-Watch.ps1'
while($true){
 try{
  & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watch
 }catch{
  Add-Content 'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\continuous_autonomy_watch.log' ('watch failure '+($_.Exception.Message))
 }
 Start-Sleep -Seconds 120
}