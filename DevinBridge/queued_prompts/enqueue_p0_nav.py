from pathlib import Path
from DevinBridge.daemon import make_coordinator, load_config
root=Path(r'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge')
wid='P0-FR-NAV-ZONE-BOUNCE-ELIGIBILITY-20261112'
file=root/'queued_prompts'/(wid+'.md')
w=root/'autonomy_scope'/'workspaces'/'foreverroute-route-audit'
checks=[{'type':'test','runner':'unittest','args':['tests.test_p0_nav_zone_eligibility'],'timeout':180},{'type':'file_contains','path':'tools/p0_nav_zone_eligibility_20261112.json','pattern':'"status"\\s*:\\s*"PASS"'}]
c=make_coordinator(load_config())
r=c.add_task(wid,'P0: Fix blocked quest navigation and cross-zone oscillation',file.read_text(encoding='utf-8'),str(w),priority=0,approved=True,scope='production',acceptance=checks,reason='Owner priority P0: unavailable Hidden Enemies and Tarren Mill/Thousand Needles/Barrens route zigzags',owner='human',generated_by='human')
print('ADDED',r.get('added'),'STATUS',r['task'].get('status'),'PRIORITY',r['task'].get('priority'),'ACCEPTANCE',r['task'].get('acceptance'))