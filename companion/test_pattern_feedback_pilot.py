import unittest
from unittest.mock import patch
import pattern_feedback_pilot as pilot
import lua_coding_lab as lab

class PatternSafetyTest(unittest.TestCase):
 def test_handwritten_calibration_84(self):
  line=pilot.assemble('%p+$')
  self.assertTrue(lab.allowed(line))
  result=pilot.hidden_verification(line)
  self.assertTrue(result['passed'],result)
  self.assertTrue(result['original_untouched'])
 def test_unapproved_patterns_rejected(self):
  for pattern in ('', '.*', '.*$', 'abc', '%s+', 'a'*60):
   with self.subTest(pattern=pattern):
    with self.assertRaises(ValueError):pilot.assemble(pattern)
 def test_incomplete_pattern_fails_hidden_gate(self):
  self.assertFalse(pilot.hidden_verification(pilot.assemble('[%.:!]+$'))['passed'])
 def test_invalid_model_response_never_edits_fixture(self):
  with patch('pattern_feedback_pilot.model_pattern',return_value='malformed'):
   result=pilot.run(1)
  self.assertFalse(result['passed_84'])
  self.assertTrue(result['original_unchanged'])
  self.assertEqual(result['attempts'][0]['status'],'REJECTED_OR_ERROR')

 def test_feedback_proves_revision_not_fake(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory(prefix='model_loop_test_') as directory:
   with patch.object(pilot,'REPORT',Path(directory)/'result.json'):
    with patch('pattern_feedback_pilot.model_pattern',side_effect=['[.!?]+$','%p+$']) as model:
     result=pilot.run(2)
  self.assertEqual(len(result['attempts']),2)
  self.assertEqual(result['attempts'][0]['status'],'FAILED_TESTS')
  self.assertIn('failed',model.call_args_list[1].args[1].lower())
  self.assertTrue(result['passed_84'])
  self.assertTrue(result['original_unchanged'])
  self.assertFalse(result['model_authored_full_patch'])
if __name__=='__main__':unittest.main()