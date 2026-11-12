"""Independent approval gates for recipe-based navigation repair."""
import unittest,hashlib
import guarded_synthesis as gs
import lua_coding_lab as lab

class GuardedSynthesisTests(unittest.TestCase):
 def test_exact_control_reaches_204(self):
  candidate=gs.assemble('%p+$')
  r=gs.property_gate(candidate)
  self.assertTrue(r['passed'],r)
  self.assertTrue(r['sources_unchanged'])
 def test_incomplete_candidate_not_promoted(self):
  candidate=gs.assemble('[%.!?]+$')
  result=gs.property_gate(candidate)
  self.assertFalse(result['passed'])
 def test_one_line_review_diff_only(self):
  source=lab.F/'ForeverRoute_UIv2.lua'
  before=lab.digest(source)
  path=gs.export_review_patch(gs.assemble('%p+$'))
  text=gs.Path(path).read_text(encoding='utf-8')
  self.assertEqual(text.count('@@ -'),1)
  self.assertEqual(len([x for x in text.splitlines() if x.startswith('+') and not x.startswith('+++')]),1)
  self.assertEqual(len([x for x in text.splitlines() if x.startswith('-') and not x.startswith('---')]),1)
  self.assertEqual(lab.digest(source),before)
 def test_report_distinguishes_rule_from_model(self):
  result=gs.synthesize()
  self.assertTrue(result['verified_204'])
  self.assertFalse(result['model_authored'])
  self.assertFalse(result['current_run_used_model'])
  self.assertTrue(result['original_unchanged'])

if __name__=='__main__':unittest.main()