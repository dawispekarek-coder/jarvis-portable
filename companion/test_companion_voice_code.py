import tempfile,unittest,wave,io
from pathlib import Path
try:
 from companion_voice import validate_audio
 from companion_coding import create_proposal
except ImportError:validate_audio=None

class VoiceCodeTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(validate_audio,'Voice/code adapters are missing')
 def test_html_is_not_accepted_as_generated_audio(self):
  with self.assertRaises(ValueError):validate_audio(b'<html>service error</html>','audio/wav')
  buf=io.BytesIO()
  with wave.open(buf,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\x00\x00'*1600)
  self.assertTrue(validate_audio(buf.getvalue(),'audio/wav')['frames']>0)
 def test_proposal_changes_only_private_copy_and_checks_source_identity(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);repo=root/'repo';repo.mkdir();source=repo/'test.lua';source.write_text('return 1\n')
   result=create_proposal(repo,root/'out','test.lua','return 1','return 2')
   self.assertEqual(source.read_text(),'return 1\n')
   self.assertEqual(Path(result['candidate']).read_text(),'return 2\n')
   self.assertIn('-return 1',Path(result['patch']).read_text())
   self.assertFalse(result['production_modified']);self.assertFalse(result['behavior_verified'])
 def test_proposal_rejects_ambiguous_replacement_and_protected_data(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);repo=root/'repo';repo.mkdir();(repo/'test.lua').write_text('return 1\nreturn 1\n')
   for path in ('DB/quest.lua','../test.lua','test.lua'):
    with self.assertRaises(ValueError):create_proposal(repo,root/'out',path,'return 1','return 2')

if __name__=='__main__':unittest.main()
