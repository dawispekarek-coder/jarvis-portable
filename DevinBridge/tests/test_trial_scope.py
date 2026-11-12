import json
import tempfile
import unittest
from pathlib import Path
from DevinBridge import cdp, trial_scope
from DevinBridge.prompt_worker import Handler

class TrialScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.worktree = self.root / 'foreverroute'
        self.worktree.mkdir()
        self.base = dict(program_id='FOREVERROUTE_CONTINUOUS_V1',
                         ongoing=True, owner_authorized=True,
                         worktrees=[str(self.worktree)],
                         kinds=['analyze','test-add','repair-small'],
                         allowed_paths=['tools','tests'])
        (self.root / 'autonomy_scope').mkdir()
        self.trial = dict(owner_authorized=True,
                          program_id=self.base['program_id'],
                          worktree=str(self.worktree),
                          starts_epoch=1000, expires_epoch=87400,
                          extra_allowed_paths=['ForeverRoute.lua',
                               'ForeverRoute_TravelTopology.lua'])
        self._write()
    def _write(self):
        (self.root/'autonomy_scope'/'CDP_PROGRAM.json').write_text(json.dumps(self.base))
        (self.root/'autonomy_scope'/'FOREVERROUTE_24H_TRIAL.json').write_text(json.dumps(self.trial))

    def test_live_trial_expands_only_exact_route_files(self):
        g=trial_scope.extend_program(self.root,self.base,now=1001)
        self.assertTrue(g['trial_active'])
        self.assertIn('ForeverRoute.lua',g['allowed_paths'])
        self.assertNotIn('DB/forever/quest.lua',g['allowed_paths'])
    def test_expiration_reverts_to_original_scope(self):
        g=trial_scope.extend_program(self.root,self.base,now=87400)
        self.assertFalse(g['trial_active'])
        self.assertEqual(g['allowed_paths'],['tools','tests'])
    def test_rejects_tampering_and_scope_expansion(self):
        self.trial['extra_allowed_paths'] += ['DB/forever/quest.lua']
        self._write()
        self.assertFalse(trial_scope.extend_program(self.root,self.base,now=2000)['trial_active'])
    def test_rejects_too_long_trial(self):
        self.trial['expires_epoch'] += 10
        self._write()
        self.assertFalse(trial_scope.extend_program(self.root,self.base,now=2000)['trial_active'])