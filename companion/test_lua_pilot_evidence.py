"""Check persisted agent evidence, never treat a fixed recipe as model success."""
import json,unittest
from pathlib import Path
import lua_coding_lab as lab
class LuaEvidenceTests(unittest.TestCase):
 def read(self,name):return json.loads((lab.ROOT/'reports'/name).read_text(encoding='utf-8'))
 def test_verified_candidate_grounded_in_current_fixture(self):
  x=self.read('coding_model_pilot.json')
  self.assertEqual(x['source_sha256'],lab.digest(lab.F/'ForeverRoute_UIv2.lua'))
  self.assertEqual(x['test_sha256'],lab.digest(lab.F/'tests'/'now_card_objectives.lua'))
  self.assertTrue(x['production_source_unchanged'])
  self.assertTrue(x['model_authored_verified'])
  self.assertTrue(any(a.get('status')=='VERIFIED' and a['test']['passed'] for a in x['attempts']))
 def test_unseen_to_model_negative_controls_reported(self):
  x=self.read('coding_holdout_pilot.json')
  self.assertTrue(x['original_unchanged'])
  self.assertNotEqual(x['returncode'],0)
  self.assertTrue(any('76 checks, 2 failed' in s for s in x['last_lines']))
 def test_qwen_refinement_did_not_pass(self):
  x=self.read('coding_refinement_pilot.json')
  self.assertFalse(x['model_authored_verified_76'])
  self.assertTrue(x['original_unchanged'])
 def test_hermes_refinement_did_not_pass(self):
  x=self.read('coding_hermes_refinement.json')
  self.assertFalse(x['model_authored_verified_76'])
  self.assertTrue(x['original_unchanged'])
if __name__=='__main__':unittest.main()