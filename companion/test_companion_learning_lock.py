import unittest,tempfile,os,json
from pathlib import Path
from unittest.mock import patch
import tool_learning as learning
class LearningLockTests(unittest.TestCase):
 def test_dead_process_lock_does_not_permanently_block_training(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'skills.sqlite';path.with_suffix('.running.lock').write_text('99999999')
   with patch.object(learning,'discover',return_value=[]):result=learning.train_all(db_path=path)
   self.assertEqual(result['status'],'COMPLETED')
 def test_live_process_lock_is_preserved(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'skills.sqlite';lock=path.with_suffix('.running.lock');lock.write_text(str(os.getpid()))
   with patch.object(learning,'discover',return_value=[]):result=learning.train_all(db_path=path)
   self.assertEqual(result['status'],'BUSY');self.assertTrue(lock.exists())
if __name__=='__main__':unittest.main()
