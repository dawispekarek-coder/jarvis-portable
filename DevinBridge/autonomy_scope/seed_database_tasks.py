"""Seed evidence-only DB tasks, unapproved until owner review."""
from pathlib import Path
from DevinBridge.daemon import make_coordinator,load_config
c=make_coordinator(load_config())
w=Path(r'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\autonomy_scope\workspaces\foreverroute-route-audit')
assert not c.worktree_holds(str(w))
base=w/'docs/autonomy/db_source_snapshot_20261109'
assert len(list(base.glob('*.md')))==7
common=('Use only isolated audit clone HEAD 5f41114; read docs/autonomy/db_source_snapshot_20261109 and the earlier three docs/autonomy audit reports. '
 'Write ONLY docs/autonomy/*.md; do not edit Lua addon files, old repos, live WoW or SavedVariables. No network, push, merges, installs or subagents. '
 'Compare 9 Nov evidence to 10 Nov fixes, dedup. EG-Link CC BY 4.0 observed interaction locations are not exact NPC spawns; '
 'Polestar/Factoruide GPL and private WDB cannot be copied into the shipped addon. One direct player observation suffices for approximate location; '
 '+/-3 yards is arrival tolerance, not source accuracy. Do not invent coordinates, quest offers or claim tested gameplay. ')
items=[]
items.append(('FR-DB-20261110-01','Reconcile Nov 9 data sources vs current route snapshot',
 'Write docs/autonomy/db_source_delta.md first line FR_DB_SOURCE_DELTA_20261110. Make an evidence matrix for Polestar, WorldDB 70862, EG-Link, Factoruide and player telemetry with date, license, build, trust class. Compare yesterday 1,317 unlocated quest IDs, 51 high and 8 stale waivers to current 5f41114 artifacts and Nov 10 prereq fixes; separate unresolved from now proven, name exact tests and missing evidence.',
 'db_source_delta.md','FR_DB_SOURCE_DELTA_20261110',['FR-SCOPE-20261110-03']))
items.append(('FR-DB-20261110-02','Prioritize still-unlocated objective navigation',
 'Write docs/autonomy/db_nav_priority.md first line FR_DB_NAV_PRIORITY_20261110. Read preceding db_source_delta.md, remaining_974_semantics.md and current 1-60 audit. Classify 423 lacking objective structure, 312 with missing positions, 188 with no metadata, and 51 events as historic counts only. Rank high fanout quests for new evidence, direct player +/-3 yard mapping, fallbacks and blocked live client proof; never invent coordinates or treat old NPC spawns as verified.',
 'db_nav_priority.md','FR_DB_NAV_PRIORITY_20261110',['FR-DB-20261110-01']))
items.append(('FR-DB-20261110-03','DB integration and client acceptance roadmap',
 'Write docs/autonomy/db_integration_gate.md first line FR_DB_INTEGRATION_GATE_20261110. Derive ordered exact implementation candidates from both DB audits, acceptance test commands, data provenance/license checks, and per-profile 1-60 live QA needs. Flag specific missing quest offers, XP pacing, saved variable interaction and 3-yard waypoint accuracy as HUMAN/IN-GAME gates. Propose code changes only; do not implement, publish or copy licensed/private data.',
 'db_integration_gate.md','FR_DB_INTEGRATION_GATE_20261110',['FR-DB-20261110-02']))
for tid,title,task,outfile,marker,deps in items:
 old=c.get_task(tid)
 if old:
  print('EXISTS',tid,old.get('status'));continue
 result=c.add_task(tid,title,common+task,str(w),priority=70,depends_on=deps,
  acceptance=[{'type':'file_exists','path':'docs/autonomy/'+outfile},
              {'type':'file_contains','path':'docs/autonomy/'+outfile,'pattern':'^'+marker}],
  approved=False,scope='production',session_mode='accept-edits',max_attempts=1,
  owner='human',generated_by='human',reason='New owner-requested Nov9 ForeverRoute DB backlog; require owner approval before auto-dispatch',
  evidence_refs=['db_sources:20261109','route_current:5f41114','scoped_audit:FR-SCOPE-20261110-03'])
 print('CREATED',tid,result.get('added'),'approved',result.get('task',{}).get('approved'))
