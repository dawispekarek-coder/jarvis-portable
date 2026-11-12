import unittest
import inspect_agent as a
class InspectTests(unittest.TestCase):
 def test_goal_selected(self):
  self.assertTrue(a.extract_goal("Prověř chyby ForeverRoute v Lua funkci FR_NowNavRepeatsTitle"))
  self.assertTrue(a.extract_goal("Oprav ForeverRoute addon"))
  self.assertFalse(a.extract_goal("Ahoj Jarvisi"))
  self.assertFalse(a.extract_goal("Nahraj to na internet"))
 def test_fixed_plan(self):
  state=a.plan({"goal":"Prověř chyby ForeverRoute v Lua funkci FR_NowNavRepeatsTitle"})
  self.assertEqual(state["steps"],["git_status","lua_symbol_search","isolated_lua_regression"])
  self.assertEqual(state["symbol"],"FR_NowNavRepeatsTitle")
  self.assertEqual(state["intent"],"review_only")
 def test_real_three_step_inspection(self):
  before=a.project_tools.status()
  state=a.inspect("Prověř chyby ForeverRoute v Lua funkci FR_NowNavRepeatsTitle")
  self.assertTrue(state["verified"])
  self.assertEqual(state["lua"]["checks"],72)
  self.assertEqual(state["lua"]["failures"],3)
  self.assertTrue(state["lua"]["fixture_unchanged"])
  self.assertTrue(state["matches"]["matches"])
  self.assertIn("pouze",a.format_report(state).casefold())
  after=a.project_tools.status()
  self.assertEqual(before["commit"],after["commit"])
  self.assertEqual(before["changed_count"],after["changed_count"])
 def test_unseen_action_stays_unavailable(self):
  with self.assertRaises(ValueError):a.inspect("Nainstaluj Chrome")
 def test_missing_evidence_fails_closed(self):
  x=a.verify({"goal":"Kontroluj ForeverRoute","intent":"review_only","steps":["git_status"]})
  self.assertFalse(x["verified"])
if __name__=="__main__":unittest.main()