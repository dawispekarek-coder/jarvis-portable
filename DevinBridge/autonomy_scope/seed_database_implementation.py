"""One-time owner-authorized code stage after verified November database docs."""
import time
from pathlib import Path
from DevinBridge.daemon import make_coordinator, load_config
c=make_coordinator(load_config())
w=Path(r'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\autonomy_scope\workspaces\foreverroute-route-audit')
assert w.is_dir() and not c.worktree_holds(str(w))
assert c.get_task('FR-SCOPE-20261110-03')['status']=='COMPLETE'
for id in ['FR-DB-20261110-01','FR-DB-20261110-02','FR-DB-20261110-03']:
 t=c.get_task(id)
 assert t and t['worktree']==str(w),(id,'unexpected worktree')
common=('Work only in the approved isolated ForeverRoute audit clone (baseline Git HEAD 5f41114), never in the Desktop Devin GUI repo. '
 'Wait for all 3 FR-DB document tasks to be VERIFIED COMPLETE before implementation. '
 'Read docs/autonomy/db_source_delta.md, db_nav_priority.md, db_integration_gate.md plus prior coverage/recalc/readiness. '
 'Respect actual WoW client and licensing limits. NEVER fabricate quest coordinates, NPC offers, objective XP or falsely certify playability. '
 'Do not copy Polestar/Factoruide GPL data or private WDB; no network, push, merge, release, install, external scripts, live WoW or SavedVariables. '
 'Do not edit DB/forever/quest.lua, DB/forever/xp.lua, Blizzard namespaces, tooltip, nameplate or actionbar. '
 'One writer per repository, do not start other agents. When evidence is insufficient, STOP and report rather than guessing. ')
items=[
 {'id':'FR-REPAIR-20261110-01','title':'Implement evidence classification validator for 1-60 DB fixes',
  'dep':['FR-DB-20261110-03'],
  'prompt':('Write a new deterministic, stdlib-only Python validator tools/route_nav_evidence_audit.py that reads allowed audit/source summary documents, '
            'classifies verifiable vs inferred vs UNKNOWN quest navigation, and outputs repeatable findings for one specified small subset. '
            'Write tests/test_route_nav_evidence_audit.py with focused positive/negative cases and docs/autonomy/implementation_phase1.md '
            'with first line FR_REPAIR_EVIDENCE_VALIDATOR. No copied third-party coordinates or speculative DB edits. '
            'Run all new unit tests and report exact validation commands. '),
  'accept':[{'type':'file_contains','path':'docs/autonomy/implementation_phase1.md','pattern':'^FR_REPAIR_EVIDENCE_VALIDATOR'},
            {'type':'file_exists','path':'tools/route_nav_evidence_audit.py'},
            {'type':'test','runner':'unittest','args':['discover','-s','tests','-p','test_route_nav_evidence_audit.py'],'expect_exit':0}]},
 {'id':'FR-REPAIR-20261110-02','title':'Implement one evidenced route navigation correctness fix with regression',
  'dep':['FR-REPAIR-20261110-01'],
  'prompt':('Using the verified database reports and the new validator, choose exactly ONE safe, reproducible code defect. '
            'Apply the minimal fix ONLY in ForeverRoute_RuntimeContract.lua, ForeverRoute_QuestExpedition.lua, or ForeverRoute_PlannerV4.lua. '
            'Do not alter or invent DB records or other Lua code. Add tests/test_runtime_nav_confidence.lua that exercises the defect with a real failing-before/passing-after case. '
            'Create docs/autonomy/implementation_phase2.md beginning FR_REPAIR_ONE_VERIFIED_FIX, citing source evidence, the exact diff, test commands and limitations. '
            'If no suitable proven fix exists, document the HUMAN/IN-GAME blocker without faking acceptance; stop for review. '),
  'accept':[{'type':'file_contains','path':'docs/autonomy/implementation_phase2.md','pattern':'^FR_REPAIR_ONE_VERIFIED_FIX'},
            {'type':'file_exists','path':'tests/test_runtime_nav_confidence.lua'},
            {'type':'test','runner':'python','args':['tools/lua51/lua51_runtime.py','run','tests/test_runtime_nav_confidence.lua'],'expect_exit':0},
            {'type':'test','runner':'python','args':['tools/lua51/compile_all.py'],'expect_exit':0}]}
]
for spec in items:
 old=c.get_task(spec['id'])
 if old:
  assert old.get('prompt_sha') and old.get('worktree')==str(w),spec['id']
  print('EXISTS',spec['id'],old['status']);continue
 res=c.add_task(spec['id'],spec['title'],common+spec['prompt'],str(w),
  priority=80,depends_on=spec['dep'],acceptance=spec['accept'],
  approved=True,scope='production',session_mode='accept-edits',
  max_attempts=1,deadline_epoch=time.time()+24*3600,
  owner='human',generated_by='human',
  reason='Explicit 2026-11-10 approval: implement after 3 verified DB reports, one guarded small fix only',
  evidence_refs=['source:20261109','baseline:5f41114','db_ready:FR-DB-20261110-03'])
 assert res.get('added'),res
 print('CREATED',spec['id'],res['task']['status'])
for id in ['FR-DB-20261110-01','FR-DB-20261110-02','FR-DB-20261110-03']:
 r=c.approve(id) if not c.get_task(id).get('approved') else {'ok': True, 'task': c.get_task(id)}
 assert r.get('ok') and r.get('task',{}).get('approved') is True,(id,r)
 print('APPROVED',id,r.get('status'))
print('READY: DB verification -> tool/validation -> one reversible code fix')
