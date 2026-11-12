import tempfile,unittest,threading,time
from pathlib import Path
try:
 from companion_store import Store
except ImportError:
 Store=None

class StoreTests(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(Store,'Durable companion store is not implemented')
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'state.sqlite';self.s=Store(self.path)
 def tearDown(self):
  if hasattr(self,'tmp'):self.tmp.cleanup()
 def test_conversation_and_idempotent_submission_survive_reopen(self):
  c=self.s.conversation('desktop');a=self.s.submit(c,'Zkontroluj Git','request-1')
  b=Store(self.path).submit(c,'Zkontroluj Git','request-1')
  self.assertEqual(a['id'],b['id']);self.assertEqual(len(self.s.history(c)),1)
  self.assertEqual(Store(self.path).conversation('desktop'),c)
 def test_claim_is_atomic_across_workers(self):
  c=self.s.conversation('desktop');self.s.submit(c,'Prace','req')
  found=[]
  def claim():found.append(Store(self.path).claim('worker',lease_seconds=30))
  ts=[threading.Thread(target=claim) for _ in range(4)]
  for t in ts:t.start()
  for t in ts:t.join()
  self.assertEqual(sum(x is not None for x in found),1)
 def test_cancelled_task_cannot_publish_late_success(self):
  c=self.s.conversation('desktop');t=self.s.submit(c,'Dlouha prace','req')
  self.s.claim('w');self.s.cancel(t['id'])
  self.s.finish(t['id'],'VERIFIED','Pozdni odpoved')
  self.assertEqual(self.s.get(t['id'])['status'],'CANCELLED')
  self.assertEqual(len(self.s.history(c)),1)
 def test_checkpointed_tool_result_not_executed_twice(self):
  c=self.s.conversation('desktop');t=self.s.submit(c,'Pamet','req');self.s.claim('w')
  self.assertIsNone(self.s.begin_tool(t['id'],'call-1','memory_save',{'text':'A'},True))
  self.s.complete_tool(t['id'],'call-1',{'saved':True})
  self.assertEqual(self.s.begin_tool(t['id'],'call-1','memory_save',{'text':'A'},True),{'saved':True})
 def test_uncertain_write_is_not_replayed_after_expired_lease(self):
  c=self.s.conversation('desktop');t=self.s.submit(c,'Zapis','req');self.s.claim('w',lease_seconds=-1)
  self.s.begin_tool(t['id'],'call-1','artifact_write',{'name':'a'},True)
  self.s.recover()
  self.assertEqual(self.s.get(t['id'])['status'],'NEEDS_REVIEW')
  self.assertIsNone(self.s.claim('new'))
 def test_repeated_write_with_new_call_id_returns_same_evidence(self):
  c=self.s.conversation('desktop');t=self.s.submit(c,'Plan','req');self.s.claim('w')
  self.s.begin_tool(t['id'],'a','schedule_task',{'goal':'Check'},True);self.s.complete_tool(t['id'],'a',{'ok':True,'id':'one'})
  self.assertEqual(self.s.begin_tool(t['id'],'b','schedule_task',{'goal':'Check'},True),{'ok':True,'id':'one'})
 def test_continue_reuses_checkpoint_without_repeating_direct_action(self):
  c=self.s.conversation('desktop');t=self.s.submit(c,'Nauc se','req');self.s.claim('w')
  self.s.checkpoint(t['id'],{'direct':'learn_czech','messages':[{'role':'user','content':'Nauc se'}],'used_tools':['learn_czech'],'steps':8})
  self.s.finish(t['id'],'PARTIAL','Zkouska probehla')
  self.s.resume(t['id']);current=self.s.get(t['id'])
  self.assertEqual(current['status'],'QUEUED');self.assertNotIn('direct',current['state']);self.assertTrue(current['state']['resumed'])
 def test_expired_read_resumes_with_checkpoint(self):
  c=self.s.conversation('desktop');t=self.s.submit(c,'Cteni','req');self.s.claim('w',lease_seconds=-1)
  self.s.begin_tool(t['id'],'call-1','web_search',{'query':'lua'},False)
  self.s.recover();self.assertEqual(self.s.get(t['id'])['status'],'QUEUED')
 def test_schedule_slot_enqueued_once_and_persists(self):
  c=self.s.conversation('desktop');schedule=self.s.schedule(c,'Zkontroluj Git',time.time()-1,60)
  self.s.tick();Store(self.path).tick()
  self.assertEqual(len(self.s.tasks(c)),1)
  self.assertGreater(self.s.schedules(c)[0]['next_run'],time.time())
 def test_too_frequent_schedule_rejected(self):
  with self.assertRaises(ValueError):self.s.schedule(self.s.conversation('a'),'test',time.time(),1)
 def test_preferences_can_be_corrected(self):
  self.s.remember('style','Odpovidej strucne','user');self.s.remember('style','Odpovidej podrobne','user')
  self.assertEqual(self.s.memories('style')[0]['value'],'Odpovidej podrobne')
 def test_past_conversation_search_is_durable_and_private(self):
  c=self.s.conversation('desktop');other=self.s.conversation('other');t=self.s.submit(c,'Studuj druidy','a');self.s.claim('w');self.s.finish(t['id'],'ANSWERED','Druid má tři formy.')
  self.s.submit(other,'Soukromé heslo druida','b')
  hits=Store(self.path).search_history(c,'druid')
  self.assertTrue(any('tři formy' in x['content'] for x in hits));self.assertFalse(any('heslo' in x['content'] for x in hits))
 def test_expired_execution_token_cannot_mutate_reclaimed_task(self):
  c=self.s.conversation('desktop');t=self.s.submit(c,'Work','req');old=self.s.claim('old',lease_seconds=-1)
  self.s.recover();new=self.s.claim('new')
  with self.assertRaises(InterruptedError):self.s.begin_tool(t['id'],'c1','artifact_write',{},True,token=old['owner'])
  with self.assertRaises(InterruptedError):self.s.checkpoint(t['id'],{'fake':True},token=old['owner'])
  with self.assertRaises(InterruptedError):self.s.finish(t['id'],'VERIFIED','wrong',token=old['owner'])
  self.assertEqual(self.s.get(t['id'])['owner'],new['owner'])
 def test_approval_bound_to_exact_tool_call(self):
  c=self.s.conversation('desktop');t=self.s.submit(c,'Formular','req');self.s.claim('w')
  self.s.wait_approval(t['id'],{'id':'c1','name':'browser_fill','arguments':{'ref':'e1','text':'A'}})
  self.s.approve(t['id']);self.assertEqual(self.s.get(t['id'])['status'],'QUEUED')
  self.assertTrue(self.s.approved(t['id'],'c1','browser_fill',{'ref':'e1','text':'A'}))
  self.assertFalse(self.s.approved(t['id'],'c1','browser_fill',{'ref':'e2','text':'B'}))

if __name__=='__main__':unittest.main()
