"""Only explicit owner regrant reopens an expired legacy recovery."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from DevinBridge import recovery

class RegrantTests(unittest.TestCase):
    def exercise(self, authorized):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            wt=root/'repo';wt.mkdir()
            scope=root/'autonomy_scope';scope.mkdir()
            grant=dict(program_id='TEST-CONTINUOUS',ongoing=True,
                       owner_authorized=True,worktrees=[str(wt)],
                       kinds=['repair-small','analyze'],
                       allowed_paths=['tools','docs/autonomy','tests'],
                       attempts_per_task=2,max_tokens=10000,
                       legacy_recovery_task_ids=(['FR-LIVE-20261111-04'] if authorized else []))
            (scope/'CDP_PROGRAM.json').write_text(json.dumps(grant))
            task=dict(id='FR-LIVE-20261111-04',status='FAILED',
                      scope='production',approved=True,worktree=str(wt),
                      program_id=None,
                      prompt='Do not write DB/generated.',
                      acceptance=[dict(type='file_exists',path='tools/route_recalc_results_20261111.json')],
                      recovery=dict(state='WAITING_HUMAN',
                                    wait_reason='grant rejected: authorization expired'))
            events=[]
            def mutate(task_id, f):
                self.assertEqual(task_id,task['id'])
                f(task)
            fake=SimpleNamespace(root=root,list_tasks=lambda:[task],
                get_task=lambda id:task if id==task['id'] else None,
                _mutate=mutate,_event=lambda *a,**k:events.append(a))
            calls=[]
            with patch.object(recovery,'maybe_spawn_recovery',
                    side_effect=lambda *a,**kw:calls.append(a) or {'spawned':False}):
                recovery.tick(fake)
            self.assertEqual(task['recovery']['state'],
                  'RETRY_AUTHORIZED' if authorized else 'WAITING_HUMAN')
            self.assertEqual(bool(calls),authorized)
            self.assertEqual(bool(events),authorized)
    def test_exact_owner_regrant_reopens(self):
        self.exercise(True)
    def test_absent_regrant_stays_blocked(self):
        self.exercise(False)