import unittest,runpy
from pathlib import Path
from unittest.mock import patch
class LegacyImportTests(unittest.TestCase):
 def test_manual_live_checks_do_not_connect_to_other_servers_on_import(self):
  for name in ('test_browser_live_once.py','test_goal_gateway_live_20261027.py','test_goal_gateway_prod_20261027.py','test_tool_learning_live_7411.py'):
   with self.subTest(name=name),patch('websockets.connect',side_effect=AssertionError('import attempted a live connection')):
    runpy.run_path(str(Path(__file__).with_name(name)))
if __name__=='__main__':unittest.main()
