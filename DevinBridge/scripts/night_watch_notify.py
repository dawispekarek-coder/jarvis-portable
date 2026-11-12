"""Send one bounded nightly health alert to already connected ntfy channel."""
from pathlib import Path
import os,sys
from DevinBridge.notify import Notifier
body=os.environ.get('JARVIS_NIGHT_ALERT','')[:850]
if not body:
    print('missing alert',file=sys.stderr)
    raise SystemExit(2)
notify=Notifier(Path(r'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge'))
result=notify._send_raw('Jarvis: overnight attention needed',body,'4','warning,robot')
print('NTFY_OK' if result else 'NTFY_FAILED')
raise SystemExit(0 if result else 3)
