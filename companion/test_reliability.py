"""Reliability regression tests for V2 real task lifecycle."""
import sys,time,threading,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import task_engine as mod

class V2ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='v2_safety_',dir=Path(__file__).parent)
        self.path=Path(self.tmp.name)/'state.db'
        self.engine=mod.Engine(self.path)
    def tearDown(self):
        self.tmp.cleanup()

    def test_atomic_claim_exactly_once(self):
        task=self.engine.create('arithmetic','2+2')
        entered=threading.Event()
        release=threading.Event()
        counts=[]
        done=[]
        def slow_work(s,store=None):
            counts.append(1)
            entered.set()
            self.assertTrue(release.wait(4))
            return {**s,'answer':'Dva plus dva jsou čtyři.','evidence':{'value':4}}
        with patch.object(mod,'do_work',side_effect=slow_work):
            worker=mod.Engine(self.path)
            t=threading.Thread(target=lambda:done.append(worker.run(task['id'])))
            t.start()
            try:
                self.assertTrue(entered.wait(4))
                second=self.engine.run(task['id'])
                self.assertEqual(second['status'],'RUNNING')
            finally:
                release.set()
                t.join(5)
            self.assertFalse(t.is_alive())
            self.assertEqual(sum(counts),1)
            self.assertEqual(done[0]['status'],'VERIFIED')

    def test_cancel_kills_owned_lua_process(self):
        task=self.engine.create('lua_audit','Audit testovacich dat')
        started=threading.Event()
        class FakeProc:
            killed=False
            returncode=None
            def communicate(self,timeout=None):
                started.set()
                if not self.killed:
                    time.sleep(.06)
                    raise subprocess.TimeoutExpired('lua',timeout)
                self.returncode=-9
                return '',''
            def kill(self): self.killed=True
        fake=FakeProc()
        results=[]
        with patch.object(mod.subprocess,'Popen',return_value=fake):
            t=threading.Thread(target=lambda:results.append(self.engine.run(task['id'])))
            t.start()
            try:
                self.assertTrue(started.wait(4))
                self.assertEqual(self.engine.cancel(task['id'])['status'],'CANCELLED')
            finally:
                t.join(5)
            self.assertFalse(t.is_alive())
            self.assertTrue(fake.killed)
            self.assertEqual(self.engine.store.get(task['id'])['status'],'CANCELLED')
            self.assertEqual(results[0]['status'],'CANCELLED')

    def test_expired_running_becomes_interrupted_not_verified(self):
        first=self.engine.create('arithmetic','2+2')
        second=self.engine.create('arithmetic','2+2')
        claimed,a=self.engine.store.claim(first['id'])
        self.assertTrue(claimed)
        claimed,b=self.engine.store.claim(second['id'])
        self.assertTrue(claimed)
        self.engine.store.save({**a,'started_at':time.time()-180})
        count=self.engine.recover_stale(grace_seconds=120)
        self.assertEqual(count,1)
        self.assertEqual(mod.Engine(self.path).store.get(first['id'])['status'],'INTERRUPTED')
        self.assertEqual(self.engine.store.get(second['id'])['status'],'RUNNING')
        self.assertEqual(self.engine.run(first['id'])['status'],'INTERRUPTED')

    def test_restart_marks_only_stale_jobs_interrupted(self):
        old=self.engine.create('arithmetic','2+2')
        fresh=self.engine.create('arithmetic','2+2')
        _,s=self.engine.store.claim(old['id'])
        self.engine.store.claim(fresh['id'])
        self.engine.store.save({**s,'started_at':time.time()-500})
        restarted=mod.Engine(self.path)
        self.assertEqual(restarted.recovered_interrupted,1)
        self.assertEqual(restarted.store.get(old['id'])['status'],'INTERRUPTED')
        self.assertEqual(restarted.store.get(fresh['id'])['status'],'RUNNING')
        self.assertEqual(mod.Engine(self.path).recovered_interrupted,0)
    def test_recovery_never_marks_done(self):
        task=self.engine.create('lua_audit','test')
        claimed,state=self.engine.store.claim(task['id'])
        self.assertTrue(claimed)
        self.engine.store.save({**state,'started_at':time.time()-500})
        self.engine.recover_stale(60)
        s=self.engine.store.get(task['id'])
        self.assertNotEqual(s['status'],'VERIFIED')
        self.engine.store.save({**s,'status':'VERIFIED'})
        self.assertEqual(self.engine.store.get(task['id'])['status'],'INTERRUPTED')

    def test_checkpoint_survives_new_engine_instance(self):
        from langgraph.checkpoint.sqlite import SqliteSaver
        task=self.engine.create('arithmetic','2+2')
        done=self.engine.run(task['id'])
        self.assertEqual(done['status'],'VERIFIED')
        new_engine=mod.Engine(self.path)
        checkdb=str(self.path.with_suffix('.graph.sqlite'))
        with SqliteSaver.from_conn_string(checkdb) as saver:
            graph=mod.make_graph(new_engine.store,checkpointer=saver)
            snap=graph.get_state({'configurable':{'thread_id':task['id']}})
        self.assertEqual(snap.values['status'],'VERIFIED')
        self.assertEqual(new_engine.store.get(task['id'])['status'],'VERIFIED')

    def test_unapproved_coding_never_claimed(self):
        t=self.engine.create('coding_proposal','Oprav kod')
        self.assertEqual(self.engine.run(t['id'])['status'],'WAITING_APPROVAL')
        claimed,_=self.engine.store.claim(t['id'])
        self.assertFalse(claimed)
        self.engine.approve(t['id'])
        self.assertEqual(self.engine.run(t['id'])['error'],'coding_agent_not_connected')

if __name__=='__main__':unittest.main(verbosity=2)
