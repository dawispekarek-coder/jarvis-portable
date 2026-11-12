"""Handwritten control candidate to calibrate evaluator, NOT model success."""
import unittest
import lua_coding_lab as lab
import knowledge_coding_gate as gate

class CalibrationTest(unittest.TestCase):
 def test_handwritten_reference_is_accepted_by_native_lua(self):
  proposal=lab.OLD[:-1]+':gsub("%p+$", ""))'
  proposal=proposal.replace(', ""',',""')
  self.assertTrue(lab.allowed(proposal),repr(proposal))
  result=gate.evaluate_candidate(proposal)
  self.assertEqual(result['status'],'VERIFIED_76',result)
  self.assertTrue(result['source_fixture_unchanged'])
  self.assertTrue(result['test_unchanged_during_run'])

if __name__=='__main__':unittest.main()