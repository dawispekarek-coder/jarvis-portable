"""Permanent autonomy grant and forbidden-path safety regression tests."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from DevinBridge import cdp
from DevinBridge.prompt_worker import Handler


class ContinuousMandateTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.wt = self.root / 'repo'
        self.wt.mkdir()
        self.scope = self.root / 'autonomy_scope'
        self.scope.mkdir()
        self.g = dict(program_id='CONTINUOUS-TEST', ongoing=True,
                      owner_authorized=True, worktrees=[str(self.wt)],
                      kinds=['analyze','repair-small'],
                      allowed_paths=['tools','tests','docs/autonomy'],
                      max_dispatches_per_hour=2, max_failures_per_24h=6)
        self.coord = SimpleNamespace(root=self.root, global_holds=lambda: [])
        self.save()

    def save(self):
        (self.scope/'CDP_PROGRAM.json').write_text(json.dumps(self.g))

    def test_permanent_grant_no_expiry_required(self):
        self.assertEqual(cdp._load_program(self.coord)['program_id'], 'CONTINUOUS-TEST')
        self.g['owner_authorized'] = False; self.save()
        self.assertFalse(cdp._load_program(self.coord))
        self.g['owner_authorized'] = True
        self.g['kinds'] = ['publish']; self.save()
        self.assertFalse(cdp._load_program(self.coord))

    def test_write_path_is_bound_to_grant(self):
        h=Handler.__new__(Handler)
        h.task={'program_id':'CONTINUOUS-TEST','worktree':str(self.wt)}
        h.coord=self.coord
        self.assertTrue(h._program_write_allowed(self.wt/'tools'/'report.py'))
        self.assertTrue(h._program_write_allowed(self.wt/'docs'/'autonomy'/'audit.md'))
        self.assertFalse(h._program_write_allowed(self.wt/'DB'/'forever'/'quest.lua'))
        self.assertFalse(h._program_write_allowed(self.wt/'DB'/'forever'/'xp.lua'))
        self.assertFalse(h._program_write_allowed(self.wt/'secret.txt'))
        self.assertFalse(h._program_write_allowed(self.root/'outside.txt'))
    def test_hourly_rate_not_lifetime_limit(self):
        stamp=datetime.now(timezone.utc).isoformat()
        jobs={f'task{i}':{'id':f'task{i}', 'status':'COMPLETE',
             'program_id':'CONTINUOUS-TEST','created_at':stamp} for i in range(2)}
        self.coord._load=lambda:{'tasks':jobs}
        r=cdp.handoff_tick(self.coord)
        self.assertFalse(r['handoff'])
        self.assertIn('hourly pacing',r['reason'])
        old=(datetime.now(timezone.utc)-timedelta(days=4)).isoformat()
        for x in jobs.values():x['created_at']=old
        r=cdp.handoff_tick(self.coord)
        self.assertFalse(r['handoff'])
        self.assertEqual(r['reason'],'no in-program proposal')
        self.assertNotIn('task budget',r['reason'])

    def test_ongoing_mandate_respects_pause(self):
        self.coord.global_holds=lambda: ['bridge paused by owner']
        result=cdp.handoff_tick(self.coord)
        self.assertFalse(result['handoff'])
        self.assertIn('paused',result['reason'])

    def test_safe_regression_command_only(self):
        from DevinBridge.cdp_loop import discover_test_results
        fixture=self.root/'nav_tests.json'
        fixture.write_text(json.dumps({'tests':[
            {'name':'nav_failure','ok':False,'error':'assert 1 == 2',
             'rerun':'python -m unittest discover -s tests -p test_route_nav_evidence_audit.py'},
            {'name':'injected','ok':False,'error':'bad command',
             'rerun':'python -c "import os; os.remove(\"important\")"',
             'fix_file':'docs/autonomy/human_review.md'}]}))
        issues=discover_test_results(fixture)
        self.assertEqual(issues[0]['acceptance'][0]['type'],'test')
        self.assertEqual(issues[0]['acceptance'][0]['runner'],'unittest')
        self.assertEqual(issues[1]['acceptance'][0]['type'],'file_exists')

    def test_failure_circuit_breaker(self):
        timestamp=datetime.now(timezone.utc).isoformat()
        jobs={f'task{i}':{'id':f'task{i}','status':'FAILED',
              'program_id':'CONTINUOUS-TEST','created_at':timestamp}
              for i in range(6)}
        self.coord._load=lambda:{'tasks':jobs}
        r=cdp.handoff_tick(self.coord)
        self.assertFalse(r['handoff'])
        self.assertIn('hourly pacing',r['reason'])
        old=(datetime.now(timezone.utc)-timedelta(hours=3)).isoformat()
        for x in jobs.values():x['created_at']=old
        r=cdp.handoff_tick(self.coord)
        self.assertIn('failure circuit breaker',r['reason'])


if __name__=='__main__':
    unittest.main()

class LegacyRecoveryOwnerScopeTests(ContinuousMandateTests):
    def test_exact_preapproved_legacy_recovery_scope(self):
        from DevinBridge import recovery
        self.g.update(legacy_recovery_task_ids=['FR-HYJAL-20261111-02'],
                      allowed_paths=['tools','tests','docs/autonomy','Generated'],
                      attempts_per_task=2,max_tokens=100000)
        self.save()
        allowed={'id':'FR-HYJAL-20261111-02','program_id':None,
                 'approved':True,'scope':'production','worktree':str(self.wt)}
        grant=recovery._auth_for(self.coord,str(self.wt),allowed)
        self.assertEqual(grant['program_id'],'CONTINUOUS-TEST')
        ok,reason=recovery.check_grant(grant,allowed,
                  {'paths':['Generated/ForeverRoute_Hyjal_Supplement.lua','tools/hyjal_quest_inventory.py']})
        self.assertTrue(ok,reason)
        for invalid in ({**allowed,'id':'FR-HYJAL-20261111-03'},
                        {**allowed,'approved':False},
                        {**allowed,'worktree':str(self.root/'unapproved')},
                        {**allowed,'scope':'test'}):
            ok,_=recovery.check_grant(grant,invalid,{'paths':['tools/audit.py']})
            self.assertFalse(ok,invalid)
        ok,_=recovery.check_grant(grant,allowed,{'paths':['DB/forever/quest.lua']})
        self.assertFalse(ok)
