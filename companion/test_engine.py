"""Independent v2 task contract acceptance tests."""
import tempfile,unittest,sys,sqlite3
from contextlib import closing
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from task_engine import Engine,State,ROOT,FIXTURE,digest

class TaskEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='v2_test_',dir=Path(__file__).parent)
        self.path=Path(self.tmp.name)/'events.db'
        self.runner=Engine(self.path)
    def tearDown(self):self.tmp.cleanup()
    def test_two_plus_two_verified(self):
        s=self.runner.create('arithmetic','kolik je dva plus dva?')
        r=self.runner.run(s['id'])
        self.assertEqual(r['status'],'VERIFIED')
        self.assertEqual(r['evidence']['value'],4)
    def test_bad_arithmetic_fails(self):
        s=self.runner.create('arithmetic','vypočítej odmocninu z 7')
        self.assertEqual(self.runner.run(s['id'])['status'],'FAILED')
    def test_coding_needs_permission(self):
        s=self.runner.create('coding_proposal','Oprav Lua')
        r=self.runner.run(s['id'])
        self.assertEqual(r['status'],'WAITING_APPROVAL')
        self.assertFalse(r['approved'])
        self.assertEqual(self.runner.approve(s['id'])['approved'],True)
        self.assertEqual(self.runner.run(s['id'])['status'],'FAILED')
    def test_cancel_pending_no_execution(self):
        s=self.runner.create('lua_audit','Zastav test')
        self.assertEqual(self.runner.cancel(s['id'])['status'],'CANCELLED')
        self.assertEqual(self.runner.run(s['id'])['status'],'CANCELLED')
    def test_unknown_tool_rejected(self):
        s=self.runner.create('run_powershell','Spusť příkaz')
        r=self.runner.run(s['id'])
        self.assertEqual(r['status'],'FAILED')
        self.assertEqual(r['error'],'kind_not_allowed')
    def test_durable(self):
        s=self.runner.create('arithmetic','2+2')
        self.runner.run(s['id'])
        self.assertEqual(Engine(self.path).store.get(s['id'])['status'],'VERIFIED')
        with closing(sqlite3.connect(self.path)) as db:
            self.assertGreater(db.execute('select count(*) from events').fetchone()[0],1)
    def test_lua_failure_no_mutation(self):
        target=FIXTURE/'ForeverRoute_UIv2.lua';test=FIXTURE/'tests'/'now_card_objectives.lua'
        before=(digest(target),digest(test))
        s=self.runner.create('lua_audit','Kontrola Lua')
        r=self.runner.run(s['id'])
        self.assertEqual(r['status'],'FAILED')
        self.assertIn('72 checks, 3 failed',r['answer'])
        self.assertTrue(r['evidence']['unchanged'])
        self.assertEqual(before,(digest(target),digest(test)))
    def test_cancel_cannot_be_overwritten(self):
        s=self.runner.create('arithmetic','2+2')
        cancelled=self.runner.cancel(s['id'])
        fake={**cancelled,'status':'VERIFIED','answer':'faked'}
        self.runner.store.save(fake)
        self.assertEqual(self.runner.store.get(s['id'])['status'],'CANCELLED')
    def test_verified_cannot_be_reopened(self):
        s=self.runner.create('arithmetic','2+2')
        done=self.runner.run(s['id'])
        self.runner.store.save({**done,'status':'RUNNING'})
        self.assertEqual(self.runner.store.get(s['id'])['status'],'VERIFIED')
if __name__=='__main__':unittest.main(verbosity=2)