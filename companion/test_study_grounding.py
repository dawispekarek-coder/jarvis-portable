import unittest
from unittest.mock import patch
import general_brain
class GroundingTests(unittest.TestCase):
 def test_project_source_priority(self):
  docs=[{'source':'RealJarvis2/JARVIS_PROVOZNI_MANUAL_V4.txt','line':1,'excerpt':'manual'},{'source':'ForeverRoute/README.md','line':15,'excerpt':'levels 1-60'}]
  with patch('general_brain.knowledge.search',return_value=docs):
   result=general_brain.source_context('ForeverRoute levels')
  self.assertEqual([x['source'] for x in result],['ForeverRoute/README.md'])
 def test_manual_not_accepted_as_project_evidence(self):
  docs=[{'source':'RealJarvis2/JARVIS_PROVOZNI_MANUAL_V4.txt','line':1,'excerpt':'manual'}]
  with patch('general_brain.knowledge.search',return_value=docs):
   with patch('general_brain.inspect_real_project',return_value={'facts':[(15,'Levels 1-60')]}):
    result=general_brain.source_context('ForeverRoute')
  self.assertEqual(result[0]['source'],'ForeverRoute/README.md')
 def test_no_fake_data_when_repo_down(self):
  with patch('general_brain.knowledge.search',return_value=[]):
   with patch('general_brain.inspect_real_project',side_effect=RuntimeError('offline')):
    self.assertEqual(general_brain.source_context('ForeverRoute'),[])