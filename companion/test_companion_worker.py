import tempfile,unittest,sys,time
from pathlib import Path
from companion_store import Store
try:
 from companion_worker import Worker
except ImportError:Worker=None

class WorkerTests(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(Worker,'Background task worker is not implemented')
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.s=Store(self.root/'db');self.c=self.s.conversation('desktop')
 def tearDown(self):
  if hasattr(self,'w'):self.w.close()
  if hasattr(self,'tmp'):self.tmp.cleanup()
 def test_accepted_task_runs_without_websocket_connection(self):
  marker=self.root/'finished';script=self.root/'job.py'
  script.write_text("import pathlib,time;time.sleep(.1);pathlib.Path("+repr(str(marker))+").write_text('ran')")
  t=self.s.submit(self.c,'test')
  self.w=Worker(self.s,command=lambda task:[sys.executable,str(script)],root=self.root)
  self.w.step();deadline=time.time()+5
  while not marker.exists() and time.time()<deadline:time.sleep(.03);self.w.step()
  self.assertEqual(marker.read_text(),'ran')
 def test_cancel_terminates_owned_job(self):
  marker=self.root/'should_not_exist';script=self.root/'job.py'
  script.write_text("import pathlib,time;time.sleep(3);pathlib.Path("+repr(str(marker))+").write_text('wrong')")
  t=self.s.submit(self.c,'test');self.w=Worker(self.s,command=lambda task:[sys.executable,str(script)],root=self.root)
  self.w.step();process=self.w.process;self.s.cancel(t['id']);self.w.step()
  self.assertIsNotNone(process.poll());self.assertFalse(marker.exists());self.assertEqual(self.s.get(t['id'])['status'],'CANCELLED')
 def test_second_worker_cannot_start_same_queue(self):
  self.w=Worker(self.s,root=self.root)
  self.assertTrue(self.w.acquire());other=Worker(Store(self.root/'db'),root=self.root)
  self.assertFalse(other.acquire())

if __name__=='__main__':unittest.main()
