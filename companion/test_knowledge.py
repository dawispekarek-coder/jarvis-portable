"""Local knowledge layer: evidence, citations and input safety."""
import unittest
import knowledge

class TestKnowledge(unittest.TestCase):
    def test_index_populated(self):
        status=knowledge.status()
        self.assertTrue(status['ready'])
        self.assertGreaterEqual(status['documents'],20)
        self.assertGreaterEqual(status['chunks'],50)
    def test_current_beta_coverage(self):
        results=knowledge.search('Jaké levely pokrývá beta ForeverRoute?')
        self.assertTrue(results)
        self.assertEqual(results[0]['source'],'ForeverRoute/README.md')
        self.assertIn('1-60',results[0]['excerpt'])
        self.assertGreater(results[0]['line'],0)
    def test_planner_sources(self):
        results=knowledge.search('Planner V4')
        self.assertTrue(any('PLANNER_V4' in x['source'] for x in results))
    def test_nonexistent_is_not_hallucinated(self):
        self.assertEqual(knowledge.search('zxcvnothere39819'),[])
        self.assertIn('nenašel',knowledge.format_answer('zxcvnothere39819'))
    def test_search_escaping(self):
        self.assertIsInstance(knowledge.search('" OR "*" ) DROP TABLE kb;--'),list)
    def test_length_limit(self):
        self.assertEqual(knowledge.search('x'*251),[])
    def test_source_labels_and_limit(self):
        rows=knowledge.search('ForeverRoute beta',limit=3)
        self.assertLessEqual(len(rows),3)
        self.assertTrue(all('source' in row and 'line' in row for row in rows))

if __name__=='__main__':unittest.main()