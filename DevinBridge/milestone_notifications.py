"""Send one ntfy milestone per finalized, pre-approved scoped audit task.
Only FR-SCOPE-20261110 tasks; never infer completion from agent prose.
"""
from pathlib import Path
from .bridge_store import read_json, atomic_write_json
from .notify import Notifier

PREFIX = 'FR-SCOPE-20261110-'

def notify_scoped_milestones(coord):
    path = coord.root / 'autonomy_scope' / 'milestone_notified.json'
    known = read_json(path, {}) or {}
    notifier = Notifier(coord.root)
    changed = False
    tasks = coord.list_tasks()
    for task in tasks:
        tid, status = task.get('id',''), task.get('status','')
        if not tid.startswith(PREFIX) or status not in ('COMPLETE','FAILED','BLOCKED'):
            continue
        signature = status + ':' + str(task.get('attempts',0))
        if known.get(tid) == signature:
            continue
        if status == 'COMPLETE':
            checks = (task.get('evidence') or {}).get('checks') or []
            if not checks or not all(c.get('ok') for c in checks):
                continue
            downstream = next((t.get('title','') for t in tasks
                               if tid in t.get('depends_on',[])
                               and t.get('status') in ('PENDING','READY')), '')
            result = notifier.task_completed(task.get('title',tid),
                                             'acceptance checks passed', downstream)
        else:
            result = notifier.task_failed(task.get('title',tid),
                     'status '+status, 'Review evidence and choose next action')
        if result.get('sent'):
            known[tid] = signature
            changed = True
    if changed:
        atomic_write_json(path, known)
