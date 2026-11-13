"""Isolated fake deployment tests: NO live WoW activity."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import auto_liveqa as a

class OrchestrationTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
  folder=Path(self.t.name)
  for target,name in ((a,'STATE'),(a,'HEALTH'),(a,'LOCK')):
   mock=patch.object(target,name,folder/(name+'.json'))
   mock.start();self.addCleanup(mock.stop)
  self.mocks=[]
  for obj,name,result in ((a,'recover_orphan',False),
     (a,'safety_preflight',None),(a,'source_stable',True),
     (a,'fingerprint',('known_signature',101)),
     (a,'refresh_stage',None),(a,'offline_tests',{'lua_files':74}),
     (a,'workers_busy',False),(a.qa,'deploy_candidate',{'backup':'dummy_backup'}),
     (a.qa,'keep_verified',{'backup':'dummy_backup'}),
     (a.qa,'rollback',{'state':'RESTORED'}),
     (a.qa_observer,'collect',None),
     (a.qa,'wow_running',False)):
   p=patch.object(obj,name,return_value=result)
   m=p.start();self.addCleanup(p.stop);self.mocks.append((name,m))
 def mock(self,name):return dict(self.mocks)[name]
 def test_clean_pass_kept_with_backup(self):
  result={'state':'COMPLETE','qa':{'result':'PASS'},'protected_popup_seen':False}
  with patch.object(a.ui,'run',return_value=result):
   status=a.watch_once()
  self.assertEqual(status,'KEPT_VERIFIED')
  self.mock('keep_verified').assert_called_once()
  self.mock('rollback').assert_not_called()
  self.assertEqual(a.read_json(a.STATE)['last_result'],'KEPT_VERIFIED')
 def test_warning_restores_old_addon(self):
  result={'state':'COMPLETE','qa':{'result':'WARN'},'protected_popup_seen':False}
  with patch.object(a.ui,'run',return_value=result):
   status=a.watch_once()
  self.assertEqual(status,'ROLLBACK_NOT_CLEAN_PASS')
  self.mock('rollback').assert_called_once()
  self.mock('keep_verified').assert_not_called()
 def test_failed_client_rolls_back_when_closed(self):
  with patch.object(a.ui,'run',side_effect=RuntimeError('client issue')):
   status=a.watch_once()
  self.assertEqual(status,'ROLLED_BACK_AFTER_ERROR')
  self.mock('rollback').assert_called_once()
 def test_unchanged_signature_is_never_retested(self):
  a.write_json(a.STATE,{'last_signature':'known_signature','last_result':'KEPT_VERIFIED'})
  self.assertTrue(a.watch_once().startswith('ALREADY_TESTED'))
  self.mock('deploy_candidate').assert_not_called()

class CoordinatorBusyGuardTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  x=patch.object(a,'AGENT_ROOT',self.root)
  x.start();self.addCleanup(x.stop)
 def test_active_coordinator_blocks_deployment_even_without_worker_process(self):
  (self.root/'coordinator_state.json').write_text(
   '{"tasks":{"id":{"status":"RUNNING"}}}',encoding='utf-8')
  ps=type('Result',(),{'stdout':'','returncode':0})()
  with patch.object(a.subprocess,'run',return_value=ps):
   self.assertTrue(a.workers_busy())
 def test_failed_process_query_fails_closed(self):
  ps=type('Result',(),{'stdout':'','returncode':1})()
  with patch.object(a.subprocess,'run',return_value=ps):
   self.assertTrue(a.workers_busy())
 def test_empty_queue_is_free(self):
  (self.root/'coordinator_state.json').write_text('{"tasks":{}}',encoding='utf-8')
  ps=type('Result',(),{'stdout':'','returncode':0})()
  with patch.object(a.subprocess,'run',return_value=ps):
   self.assertFalse(a.workers_busy())
