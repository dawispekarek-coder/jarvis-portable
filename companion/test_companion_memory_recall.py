import tempfile,unittest
from pathlib import Path
from companion_store import Store

class MemoryRecallTests(unittest.TestCase):
 def test_czech_recall_survives_reopen_and_punctuation(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'memory.sqlite'; s=Store(path)
   s.remember('workflow','Lali a Pooli: uložené postupy a ověřené chyby.','user')
   s.remember('other','Nákup jablek.','user')
   for query in ('Lali?','ověřené','overene','ulozene'):
    with self.subTest(query=query):
     self.assertEqual([m['key'] for m in Store(path).memories(query)],['workflow'])
   self.assertEqual(Store(path).memories('???'),[])
   self.assertEqual(len(Store(path).memories('')),2)
