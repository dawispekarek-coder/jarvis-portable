import unittest
import lua_coding_lab as lab
class CodingSandboxTests(unittest.TestCase):
 def test_baseline_still_fails(self):
  result=lab.native(lab.F)
  self.assertFalse(result['passed'])
  self.assertIn('3 failed',result['tail'])
 def test_blank_change_rejected(self):
  self.assertFalse(lab.allowed(lab.OLD))
  self.assertFalse(lab.allowed(''))
 def test_arbitrary_lua_command_rejected(self):
  self.assertFalse(lab.allowed(lab.OLD[:-1]+':gsub("%p+$","");os.execute("calc"))'))
 def test_one_bounded_string_gsub_allowed(self):
  candidate=lab.OLD[:-1]+':gsub("%p+$",""))'
  self.assertTrue(lab.allowed(candidate))
 def test_original_fixture_checksums(self):
  source=lab.F/'ForeverRoute_UIv2.lua'
  test=lab.F/'tests'/'now_card_objectives.lua'
  before=(lab.digest(source),lab.digest(test))
  lab.native(lab.F)
  self.assertEqual((lab.digest(source),lab.digest(test)),before)
if __name__=='__main__':unittest.main()