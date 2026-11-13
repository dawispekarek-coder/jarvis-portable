"""Hermetic safety of actual-game-evidence promotion."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import qa_manager,qa_observer

class EvidenceTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory()
  self.addCleanup(tmp.cleanup)
  self.root=Path(tmp.name)
  self.qa=self.root/'live_qa';self.qa.mkdir()
  self.source=self.root/'repo';(self.source/'tools').mkdir(parents=True)
  (self.root/'coordinator_state.json').write_text(json.dumps({'tasks':{}}))
  for x in (patch.object(qa_observer,'ROOT',self.qa),
            patch.object(qa_observer,'OUT',self.qa/'status.json'),
            patch.object(qa_manager,'SOURCE',self.source)):
   x.start();self.addCleanup(x.stop)
 def test_no_client_proof_produces_no_tasks(self):
  data={'wow_running':False,'probe_installed':True,'candidate_active':False,
        'diagnostic':{'state':'NO_LIVE_RESULT'}}
  with patch.object(qa_observer,'status',lambda:data):
   result=qa_observer.collect()
  self.assertEqual(result['phase'],'WAITING_FOR_BATTLENET_PLAY_AND_CHARACTER_LOGIN')
  self.assertFalse((self.source/'tools'/'liveqa_results.json').exists())
 def test_real_failure_and_pass_yield_honest_evidence(self):
  d={'wow_running':False,'probe_installed':True,'candidate_active':False,
     'diagnostic':{'state':'LIVE_RESULT_RECORDED','age_seconds':3,
                   'result':'FAIL','health':'DIAGNOSTICS_MISSING','phase':'PLAYER_LOGOUT'}}
  with patch.object(qa_observer,'status',lambda:d):
   qa_observer.collect()
   p=self.source/'tools'/'liveqa_results.json'
   self.assertFalse(json.loads(p.read_text())['tests'][0]['ok'])
   d['diagnostic']['result']='PASS';d['diagnostic']['health']='OK'
   qa_observer.collect()
   self.assertTrue(json.loads(p.read_text())['tests'][0]['ok'])
 def test_busy_worker_blocks_evidence_write(self):
  (self.root/'coordinator_state.json').write_text(json.dumps({'tasks':{'job':{'status':'RUNNING'}}}))
  d={'wow_running':False,'probe_installed':True,'candidate_active':False,
     'diagnostic':{'state':'LIVE_RESULT_RECORDED','age_seconds':4,
                   'result':'FAIL','health':'PROBE_ERROR','phase':'PLAYER_LOGOUT'}}
  with patch.object(qa_observer,'status',lambda:d):qa_observer.collect()
  self.assertFalse((self.source/'tools'/'liveqa_results.json').exists())
