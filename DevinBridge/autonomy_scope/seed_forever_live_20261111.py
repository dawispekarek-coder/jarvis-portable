"""Owner-approved Nov 11 Forever live evidence and 1-60 development handoff."""
from pathlib import Path
from DevinBridge.daemon import make_coordinator, load_config
c = make_coordinator(load_config())
w = Path(r'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\autonomy_scope\workspaces\foreverroute-route-audit')
assert w.is_dir() and (w/'docs/autonomy/LIVE_FOREVER_20261111_MANDATE.md').is_file()
assert not c.worktree_holds(str(w)) and not c.global_holds(), 'SAFETY HOLD: no dispatch'
common = ('Read docs/autonomy/LIVE_FOREVER_20261111_MANDATE.md FIRST. '
          'This is the explicit owner mandate to work on live WoW Forever 1-60 data, coordinates and routes, not another static-only roadmap. '
          'Work only inside this isolated worktree; inspect current uncommitted changes before edits. '
          'Use public READ-ONLY online sources at reasonable request rate, track provenance/build/license; no source data copying if licensing incompatible. '
          'No live game installation edits, no external repo modifications, no private game data, no publication, no invented coordinates. '
          'Run real tests and deliver file artifacts. If a data source fails, record and continue with alternatives. ')
jobs = [
('FR-LIVE-20261111-01','Discover and validate live Forever quest/NPC/coordinate sources',
 'Implement tools/forever_live_source_inventory.py to probe only public read-only endpoints from mandate, verify source access, build freshness and licensing; actual live HTTP checks, cite URL/date, distinguish in-client/player/Classic; create docs/autonomy/live_source_matrix_20261111.md and tests/test_forever_live_source_inventory.py. Provide truthful evidence about missing fields/blocked endpoints and rerun command.',
 [],[{'type':'file_exists','path':'tools/forever_live_source_inventory.py'},
     {'type':'file_contains','path':'docs/autonomy/live_source_matrix_20261111.md','pattern':'FOREVER_LIVE_SOURCE_MATRIX_20261111'},
     {'type':'test','runner':'unittest','args':['discover','-s','tests','-p','test_forever_live_source_inventory.py'],'expect_exit':0}],5),
('FR-LIVE-20261111-02','Join current Forever quest catalog to verified fresh sources',
 'Create tools/forever_quest_gap_join.py, docs/autonomy/live_quest_gap_join_20261111.md and tests/test_forever_quest_gap_join.py. Actually enumerate all 728 route sections and quest IDs, reconcile sources via IDs; map missing pickup/turnin/objective/NPC/object/spawn/prereq/XP data, confidence and licensing. Produce machine-readable gap report in tools/live_quest_gaps_20261111.json. Run tests; quantify how many real gaps sources can cover, avoid unsupported complete claims.',
 ['FR-LIVE-20261111-01'],[{'type':'file_exists','path':'tools/forever_quest_gap_join.py'},
     {'type':'file_exists','path':'tools/live_quest_gaps_20261111.json'},
     {'type':'file_contains','path':'docs/autonomy/live_quest_gap_join_20261111.md','pattern':'FOREVER_QUEST_GAP_JOIN_20261111'},
     {'type':'test','runner':'unittest','args':['discover','-s','tests','-p','test_forever_quest_gap_join.py'],'expect_exit':0}],7),
('FR-LIVE-20261111-03','Implement licensed evidence-backed waypoint candidate overlays',
 'Start with level 1-22, then all remaining bands. Build tools/build_waypoint_candidates.py with tools/waypoint_candidates_20261111.json, tests/test_waypoint_candidates.py and docs/autonomy/waypoint_progress_20261111.md. Produce only coordinates supported by source terms and evidence (or user direct observation), preserve source IDs/build/map transforms, apply +/-3yd arrival tolerance NOT accuracy; mark UNKNOWN conflicts. Never copy mixed GPL/private records into distributable data. Run tests and state actual added count.',
 ['FR-LIVE-20261111-02'],[{'type':'file_exists','path':'tools/build_waypoint_candidates.py'},
     {'type':'file_exists','path':'tools/waypoint_candidates_20261111.json'},
     {'type':'file_contains','path':'docs/autonomy/waypoint_progress_20261111.md','pattern':'FOREVER_WAYPOINT_PROGRESS_20261111'},
     {'type':'test','runner':'unittest','args':['discover','-s','tests','-p','test_waypoint_candidates.py'],'expect_exit':0}],9),
('FR-LIVE-20261111-04','Recalculate and test real 56-profile 1-60 route optimization',
 'Independent of online sources: execute existing tools/route_recalc.lua in real Lua 5.1, capture 728-band metrics including 940->0 registry, 863->904 authored regression and 18 level inversions. Build tools/route_recalc_results_20261111.json via reproducible command and tests/test_route_recalc_results.py, docs/autonomy/recalc_progress_20261111.md. Fix smallest proven route order lifecycle defect, avoid unverified data changes, check all 728. No release/merge/deploy and no modification of protected DB/generated shipping files.',
 [],[{'type':'file_exists','path':'tools/route_recalc_results_20261111.json'},
     {'type':'file_contains','path':'docs/autonomy/recalc_progress_20261111.md','pattern':'FOREVER_ROUTE_RECALC_20261111'},
     {'type':'test','runner':'unittest','args':['discover','-s','tests','-p','test_route_recalc_results.py'],'expect_exit':0}],11)
]
for tid,title,goal,deps,accept,priority in jobs:
    old=c.get_task(tid)
    if old:
        assert old['worktree']==str(w), 'task id conflict'
        print('EXISTS',tid,old['status']);continue
    r=c.add_task(tid,title,common+goal,str(w),priority=priority,depends_on=deps,acceptance=accept,approved=True,scope='production',session_mode='accept-edits',max_attempts=2,owner='human',generated_by='human',reason='Explicit user mandate 2026-11-11 to Jarvis/Devin: research current Forever and implement routes and waypoint evidence',evidence_refs=['owner:20261111','docs/autonomy/LIVE_FOREVER_20261111_MANDATE.md'])
    assert r.get('added'), (tid,r)
    print('CREATED',tid)
first=c.get_task('FR-LIVE-20261111-01')
if first['status'] in ('PENDING','READY'):
    print('DISPATCH', c.dispatch(first['id']))
else:
    print('EXISTING_FIRST',first['status'],first.get('session_id',''))
print('SUMMARY',[(t,c.get_task(t)['status']) for t in [x[0] for x in jobs]])
