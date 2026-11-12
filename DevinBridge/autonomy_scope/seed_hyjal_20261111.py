"""Direct owner task: verify Hyjal data and integrate routes in isolated ForeverRoute."""
from pathlib import Path
from DevinBridge.daemon import make_coordinator, load_config
c=make_coordinator(load_config())
w=Path(r'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\autonomy_scope\workspaces\foreverroute-route-audit')
brief=w/'docs/autonomy/HYJAL_20261111_BRIEF.md'
assert brief.exists() and w.is_dir()
assert not c.global_holds(), 'coordinator global hold'
common=("Read docs/autonomy/HYJAL_20261111_BRIEF.md; owner requests Mount Hyjal added into actual ForeverRoute leveling routes. "
"Use approved isolated worktree ONLY; preserve current uncommitted changes, no protected DB edits, no published game/install changes. "
"Research public web endpoints via reasonable read-only GET; obey licenses, no made-up coordinates or quest ID. "
"Track version, IDs, NPCs, map transforms, route evidence and tests. Compare 36 vs 230 Hyjal entries honestly. ")
specs=[
('FR-HYJAL-20261111-01','Verify all obtainable Mount Hyjal quests, NPCs and waypoint candidates',
("Implement tools/hyjal_quest_inventory.py and write tools/hyjal_quest_inventory_20261111.json. "
"Actually query available public sources or read legally available client DB, cross-reference existing 728 routes and zoneMap 616/2482, enumerate currently available quest IDs and missing givers/objectives/turnins. "
"Research flight coords, entrance through Winterspring and 9 subareas. "
"Document proven vs doubtful facts with source/date/build/license in docs/autonomy/hyjal_source_reconcile_20261111.md beginning HYJAL_SOURCE_RECONCILED_20261111. "
"Create and run tests/test_hyjal_quest_inventory.py; add no unverified spawn coordinates."),[],
[{'type':'file_exists','path':'tools/hyjal_quest_inventory.py'},
{'type':'file_exists','path':'tools/hyjal_quest_inventory_20261111.json'},
{'type':'file_contains','path':'docs/autonomy/hyjal_source_reconcile_20261111.md','pattern':'HYJAL_SOURCE_RECONCILED_20261111'},
{'type':'test','runner':'unittest','args':['discover','-s','tests','-p','test_hyjal_quest_inventory.py'],'expect_exit':0}],2),

('FR-HYJAL-20261111-02','Integrate verified Hyjal quests and waypoints into 1-60 routes',
("Implement actual reproducible route-integration, not just documentation: use tools/hyjal_quest_inventory_20261111.json to create tools/build_hyjal_routes.py, "
"route data/overlay and needed loader registration for 50-55 or 55-60 eligible V3 profiles and safe V4. "
"Produce Generated/ForeverRoute_Hyjal_Supplement.lua from verified, compatible data; wire into actual addon route loading if safe. "
"Require verified pickup->objective->turnin chains, faction/class/level, travel edges and flight nodes, without inserting raid quests locked until Dec 9. "
"Run real Lua 5.1 regression across affected profiles and verify 728 original sections remain intact. "
"Write tests/test_hyjal_route_integration.py proving Hyjal is REGISTERED and accessible in generated guides, not just present in JSON. "
"Write docs/autonomy/hyjal_route_integration_20261111.md starting HYJAL_ROUTE_INTEGRATED_20261111, with inserted quest IDs, section counts, and missing facts. "
"If insufficient legal/verified live evidence, do not invent an integration; explicitly fail the acceptance test and name blocker."),['FR-HYJAL-20261111-01'],
[{'type':'file_exists','path':'tools/build_hyjal_routes.py'},
{'type':'file_exists','path':'Generated/ForeverRoute_Hyjal_Supplement.lua'},
{'type':'file_contains','path':'docs/autonomy/hyjal_route_integration_20261111.md','pattern':'HYJAL_ROUTE_INTEGRATED_20261111'},
{'type':'test','runner':'unittest','args':['discover','-s','tests','-p','test_hyjal_route_integration.py'],'expect_exit':0}],3)]

for tid,title,goal,deps,accept,priority in specs:
    old=c.get_task(tid)
    if old:
        assert old['worktree']==str(w), (tid,'ID_CONFLICT')
        print('EXISTS',tid,old['status'])
        continue
    r=c.add_task(tid,title,common+goal,str(w),
      priority=priority,depends_on=deps,acceptance=accept,
      approved=True,scope='production',session_mode='accept-edits',
      max_attempts=2,owner='human',generated_by='human',
      reason='2026-11-11 owner request: Mount Hyjal opened, complete database/waypoints/leveling routes',
      evidence_refs=['owner:hyjal:20261111','docs/autonomy/HYJAL_20261111_BRIEF.md'])
    assert r.get('added'),r
    print('CREATED',tid,r['task']['status'])
for sid,_,_,_,_,_ in specs:
    print('TASK',sid,c.get_task(sid)['status'])
if c.get_task(specs[0][0])['status'] in ('PENDING','READY'):
    print('DISPATCH_TRY',c.dispatch(specs[0][0]))

