import unittest,subprocess
from unittest.mock import patch
import project_tools as x
class ProjectToolTests(unittest.TestCase):
 def test_explicit_request(self):
  self.assertTrue(x.extract('Zkontroluj Git ForeverRoute'))
  self.assertTrue(x.extract('/repo'))
  self.assertFalse(x.extract('Ahoj Jarvisi'))
  self.assertFalse(x.extract('Oprav Git ForeverRoute'))
 def test_current_repo_real_read_only(self):
  result=x.status()
  self.assertTrue(result['read_only'])
  self.assertTrue(result['commit'])
  self.assertTrue(result['branch'])
  self.assertIn('Větev:',x.format_status(result))
 def test_fails_closed(self):
  with patch('project_tools.git',side_effect=RuntimeError('offline')):
   with self.assertRaises(RuntimeError): x.status()
 def test_sensitive_file_hidden(self):
  with patch('project_tools.git',side_effect=[
    str(x.REPO),'test-branch','abcdef0|2026-10-26|Test commit',
    ' M config/.env\n M scripts/task.lua']):
   result=x.status()
  self.assertIn('[sensitive filename hidden]',result['changed_files'])
  self.assertIn('scripts/task.lua',result['changed_files'][1])
 def test_no_shell_invocation(self):
  original=subprocess.run
  def watch(cmd,**kw):
   self.assertIsInstance(cmd,list)
   self.assertNotIn('shell',kw)
   self.assertEqual(cmd[1],'--no-optional-locks')
   return original(cmd,**kw)
  with patch('project_tools.subprocess.run',side_effect=watch):x.status()
 def test_code_search_explicit_and_guarded(self):
  self.assertEqual(x.extract_code_search("/code FR_NowNavRepeatsTitle"),"FR_NowNavRepeatsTitle")
  self.assertEqual(x.extract_code_search("Najdi v kódu ForeverRoute: FR_NowNavRepeatsTitle"),"FR_NowNavRepeatsTitle")
  self.assertIsNone(x.extract_code_search("Oprav soubor ForeverRoute_UIv2.lua"))
  with self.assertRaises(ValueError):x.search_lua("API_KEY")
  with self.assertRaises(ValueError):x.search_lua("../.env")
 def test_real_lua_symbol_search_is_read_only(self):
  before=x.status()
  result=x.search_lua("FR_NowNavRepeatsTitle")
  self.assertTrue(result["read_only"])
  self.assertTrue(any(z["file"].endswith(".lua") and z["line"]>0 for z in result["matches"]))
  self.assertIn("Lua kódu",x.format_code_search(result))
  after=x.status()
  self.assertEqual(before["commit"],after["commit"])
  self.assertEqual(before["changed_count"],after["changed_count"])
 def test_no_code_match_does_not_claim_found(self):
  result=x.search_lua("NoSuchFunctionAbCd4321")
  self.assertEqual(result["matches"],[])
  self.assertIn("nenašel",x.format_code_search(result))
if __name__=='__main__':unittest.main()