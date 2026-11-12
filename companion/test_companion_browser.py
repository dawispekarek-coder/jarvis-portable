import unittest,tempfile
from pathlib import Path
try:
 from companion_browser import Browser,public_destination
except ImportError:Browser=None

class BrowserTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(Browser,'Browser adapter is not implemented')
 def test_private_destinations_rejected_before_launch(self):
  for url in ('file:///etc/passwd','http://127.0.0.1:7430','https://localhost/x','https://192.168.0.1','https://example.com@localhost/x'):
   with self.assertRaises(ValueError):public_destination(url)
 def test_stale_or_unknown_refs_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   b=Browser(Path(tmp)/'profile',Path(tmp)/'out')
   for ref in ('old-e1','e1','https://example.com'):
    with self.assertRaises(ValueError):b.click(ref)
 def test_changed_destination_invalidates_approved_action(self):
  from companion_browser import validate_approval
  original={'document_id':'one','state_hash':'hash-a','url':'https://example.com','ref':'e1','href':'https://example.com/read'}
  changed={**original,'href':'https://example.com/delete'}
  with self.assertRaises(ValueError):validate_approval(original,changed)
 def test_lost_session_does_not_recreate_form_and_submit(self):
  with tempfile.TemporaryDirectory() as tmp:
   b=Browser(Path(tmp)/'profile',Path(tmp)/'out');b.out.mkdir(parents=True)
   import json
   (b.out/'browser_snapshot.json').write_text(json.dumps({'url':'https://example.com','elements':[{'ref':'e1'}]}))
   with self.assertRaisesRegex(ValueError,'session_lost'):b.click('e1',document_id='one',state_hash='hash-a')

if __name__=='__main__':unittest.main()
