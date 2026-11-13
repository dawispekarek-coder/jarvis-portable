from pathlib import Path
from DevinBridge.daemon import make_coordinator, load_config
root=Path(r'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge')
task_id='P0-FR-ROUTE-STANDARD-JARVIS-INTEGRATION-20261112'
prompt=(root/'queued_prompts'/(task_id+'.md')).read_text(encoding='utf-8')
w=root/'autonomy_scope'/'workspaces'/'foreverroute-route-audit'
checks=[{'type':'test','runner':'unittest','args':['tests.test_route_standard_supervision'],'timeout':240},{'type':'file_exists','path':'docs/route_engineering/ROUTE_STANDARD_ENFORCEMENT_PROOF.md'}]
c=make_coordinator(load_config())
r=c.add_task(task_id,'P0: Integrate route standard as enforceable Jarvis supervisor checks',prompt,str(w),priority=0,approved=True,scope='production',acceptance=checks,reason='Owner asked Devin to own and enforce route construction standard across all 56 profiles',owner='human',generated_by='human')
print('ID',task_id,'ADDED',r['added'],'STATUS',r['task']['status'],'PRIORITY',r['task']['priority'],'APPROVED',r['task']['approved'])