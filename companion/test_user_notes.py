"""Tests for explicit, provenance-labelled private notes."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from knowledge_store import NoteStore,handle_command
class NoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'notes.sqlite'
        self.store=NoteStore(self.path)
    def tearDown(self):self.tmp.cleanup()
    def test_note_persists_without_claiming_verification(self):
        note=self.store.remember('ForeverRoute je addon pro WoW')
        self.assertFalse(note['verified'])
        hits=NoteStore(self.path).search('co si pamatuješ o ForeverRoute')
        self.assertEqual(len(hits),1)
        self.assertEqual(hits[0]['origin'],'user_note')
    def test_duplicate_not_inserted(self):
        a=self.store.remember('TEST JEDNA')
        b=self.store.remember('test jedna')
        self.assertEqual(a['id'],b['id'])
        self.assertTrue(b['duplicate'])
    def test_forget_explicit_note(self):
        a=self.store.remember('Jednorázová poznámka')
        self.assertTrue(self.store.forget(a['id']))
        self.assertEqual(self.store.search('jednorázová'),[])
    def test_intent_recall(self):
        self.assertIn('Uložil',handle_command(self.store,'Zapamatuj si: Favorit je ForeverRoute'))
        result=handle_command(NoteStore(self.path),'Co si pamatuješ o ForeverRoute?')
        self.assertIn('Favorit je ForeverRoute',result)
    def test_invalid_note_rejected(self):
        with self.assertRaises(ValueError):self.store.remember('x')
        with self.assertRaises(ValueError):self.store.remember('A'*1001)
if __name__=='__main__':unittest.main()