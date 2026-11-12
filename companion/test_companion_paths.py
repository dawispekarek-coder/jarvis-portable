import unittest
from pathlib import Path
class PathIsolationTests(unittest.TestCase):
 def test_existing_adapters_keep_databases_and_fixtures_in_this_checkout(self):
  import task_engine,knowledge,experience_learning,lua_coding_lab,learning_review
  expected=Path(__file__).resolve().parent.parent
  self.assertEqual(task_engine.ROOT,expected);self.assertEqual(knowledge.ROOT,expected)
  self.assertEqual(experience_learning.DB.parent,expected/'BrainCore')
  self.assertEqual(lua_coding_lab.ROOT,expected);self.assertEqual(learning_review.ROOT,expected)
if __name__=='__main__':unittest.main()
