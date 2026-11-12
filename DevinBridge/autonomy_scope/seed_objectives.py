"""Owner-authorized finite route audit chain, standalone clone only."""
import time
from pathlib import Path
from DevinBridge.daemon import make_coordinator, load_config
c = make_coordinator(load_config())
root = Path(r'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\autonomy_scope\workspaces\foreverroute-route-audit')
assert root.is_dir() and (root/'.git').exists() and str(root.resolve()).casefold() in c.authorized_worktrees
assert c.mode == 'safe' and not c.autonomous_flag.exists()
common = ("ONLY work in this isolated offline ForeverRoute clone; your source snapshot is HEAD 5f41114. "
          "Do not access or edit any external worktree, the real World of Warcraft installation, SavedVariables, "
          "DB/forever/quest.lua, DB/forever/xp.lua, existing source files or tools. "
          "Only create/edit files under docs/autonomy/. No network, Git push, merges, publishing, installs, "
          "new subagents, elevated commands or speculative map coordinates. "
          "Clearly distinguish static evidence from in-game WoW client verification. ")

jobs = [
 ('FR-SCOPE-20261110-01', 'Audit route-data coverage levels 1-60',
  'Read Generated/ForeverRoute_V3_Sections.lua, tools/audit_56x13.py, tools/audit_56x13_findings.csv, and route-related tests. '
  'Create docs/autonomy/coverage_1to60.md with exact first line FR_SCOPED_COVERAGE_1TO60. '
  'Document supported 1-22, 23-40 and 41-60 evidence, known missing/suspect data, source file/line references, '
  'counts where you can prove them and UNKNOWN when you cannot. Do not invent gameplay claims.',
  'docs/autonomy/coverage_1to60.md','FR_SCOPED_COVERAGE_1TO60',[]),
 ('FR-SCOPE-20261110-02','Audit prerequisite consistency and recalculation blockers',
  'Read docs/autonomy/coverage_1to60.md, tools/route_recalc.lua, tests/test_prereq_repair.lua, '
  'tests/test_prereq_sanitize_real.lua, tests/test_prereq_scale.lua. '
  'Create docs/autonomy/recalc_gap_analysis.md with first line FR_SCOPED_RECALC_GAPS. '
  'Compare claimed verified fixes to gaps and list independently grounded blockers, no unsupported fixes. '
  'Focus on objective-before-pickup rules, real quest prerequisites, authored claims, missing coordinates, and XP pacing.',
  'docs/autonomy/recalc_gap_analysis.md','FR_SCOPED_RECALC_GAPS',['FR-SCOPE-20261110-01']),
 ('FR-SCOPE-20261110-03','Build evidence-backed route readiness roadmap',
  'Read BOTH docs/autonomy/coverage_1to60.md and docs/autonomy/recalc_gap_analysis.md. '
  'Create docs/autonomy/readiness_roadmap.md with first line FR_SCOPED_READINESS_ROADMAP. '
  'Prioritize next 1-60 work by impact and confidence; give exact candidate source files, test criteria, '
  'worktree ownership and human in-game QA gates. Never claim 100% playable coverage without live evidence. '
  'Conclude with finite proposed tasks and their required approval; DO NOT implement them now.',
  'docs/autonomy/readiness_roadmap.md','FR_SCOPED_READINESS_ROADMAP',['FR-SCOPE-20261110-02'])
]
for tid,title,prompt,path,marker,deps in jobs:
    t=c.get_task(tid)
    if t:
        print('ALREADY_EXISTS',tid,t['status'])
        continue
    assert not c.worktree_holds(str(root)), c.worktree_holds(str(root))
    r=c.add_task(tid,title,common+prompt,str(root),priority=30+len(deps),
        depends_on=deps,acceptance=[{'type':'file_exists','path':path},
        {'type':'file_contains','path':path,'pattern':'^'+marker}],
        approved=True,scope='production',session_mode='accept-edits',
        owner='human',reason='Owner-authorized finite isolated ForeverRoute 1-60 static audit chain 2026-11-10',
        generated_by='human',evidence_refs=['clone_snapshot:5f41114c1283'],max_attempts=1,
        deadline_epoch=time.time()+12*3600)
    print('CREATED',tid,r.get('added'),r.get('task',{}).get('status'))
print('QUEUE_READY')
