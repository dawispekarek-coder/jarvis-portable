import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import learning_review as review
import experience_learning as experiences

class Study(unittest.TestCase):
 def test_recommendations_are_evidence_based(self):
  self.assertIn('vzorku',review.recommend({'verified_observations':1,'failed_reads':0,'successful_reads':1}))
  self.assertIn('záložní',review.recommend({'verified_observations':8,'failed_reads':6,'successful_reads':2}))
 def test_review_runs_real_tests_without_source_edits(self):
  with tempfile.TemporaryDirectory(prefix='v2review_') as tmp:
   with patch.object(review,'REPORT',Path(tmp)/'audit.json'),patch.object(experiences,'DB',Path(tmp)/'outcomes.sqlite'):
    report=review.run()
    self.assertTrue(report['tests_passed'],report['test_tail'])
    self.assertFalse(report['changes_applied'])
    self.assertFalse(report['model_weights_retrained'])
    self.assertTrue((Path(tmp)/'audit.json').exists())
if __name__=='__main__':unittest.main()