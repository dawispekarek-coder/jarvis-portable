import unittest
try:
 import companion_secondary_search as search
except ImportError:
 search=None

class SecondarySearchTests(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(search, 'Secondary search adapter is not implemented')
 def test_empty_results_never_prove_originality(self):
  value=search.normalize_results('unique character pair', [], 'bing')
  self.assertFalse(value['originality_verified'])
  self.assertEqual(value['status'],'NO_RESULTS')
  self.assertEqual(value['results'],[])
 def test_results_are_only_links_and_snippets(self):
  value=search.normalize_results('animal couple', [{'title':'Example','href':'https://example.com/pair','body':'A pair'}], 'bing')
  self.assertFalse(value['originality_verified'])
  self.assertFalse(value['pages_read'])
  self.assertEqual(value['results'][0]['url'],'https://example.com/pair')
  self.assertEqual(value['status'],'RESULTS')
 def test_unsafe_and_duplicate_urls_are_filtered(self):
  raw=[{'href':u,'title':'Pair'} for u in ['file:///a','http://localhost/x','https://127.0.0.1/a','https://example.com/a','https://example.com/a']]
  self.assertEqual(len(search.normalize_results('animal couple',raw,'bing')['results']),1)
 def test_query_length_is_bounded(self):
  for q in ['', 'x'*301, None]:
   with self.assertRaises(ValueError):search.validate_query(q)

if __name__=='__main__':unittest.main()


class IntegrationTests(unittest.TestCase):
 def test_explicit_secondary_query_routes_to_new_tool(self):
  from companion_agent import known_call
  result=known_call('Druhé hledání: cute animal couples',{'web_search_secondary'})
  self.assertIsNotNone(result)
  self.assertEqual(result['name'],'web_search_secondary')
  self.assertEqual(result['arguments']['query'],'cute animal couples')
 def test_empty_search_formats_as_uncertain_not_unique(self):
  from companion_agent import format_evidence
  text=format_evidence('web_search_secondary',{'ok':True,'value':{'results':[]}})
  self.assertIn('neprokazuje',text)
  self.assertNotIn('results',text)

