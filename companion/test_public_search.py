import unittest
from unittest.mock import patch
import public_search as web
class SearchTests(unittest.TestCase):
 def test_explicit_web_intent(self):
  self.assertEqual(web.extract_request("Vyhledej na internetu LangGraph dokumentaci"),"LangGraph dokumentaci")
  self.assertEqual(web.extract_request("/web LangGraph"),"LangGraph")
  self.assertIsNone(web.extract_request("Najdi obrázky kačiček"))
 def test_link_decoding(self):
  link="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdocs.langchain.com%2Foss%2Fpython%2Flanggraph"
  self.assertEqual(web.destination(link),"https://docs.langchain.com/oss/python/langgraph")
  self.assertIsNone(web.destination("javascript:alert(1)"))
  self.assertIsNone(web.destination("https://127.0.0.1/secrets"))
 def test_parse_relevance_and_honesty(self):
  html='<html><a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdocs.langchain.com%2Foss%2Flanggraph">LangGraph official docs</a><a href="https://example.com/chrome">Google Chrome download</a></html>'
  results=web.parse_results(html,"LangGraph Python")
  self.assertEqual(len(results),1)
  self.assertIn("langgraph",results[0]["url"])
  self.assertNotIn("Chrome",web.format_results({"query":"LangGraph","results":results}))
 def test_bot_guard(self):
  with self.assertRaises(web.SearchUnavailable):web.parse_results("Please complete the CAPTCHA", "LangGraph")
 def test_no_fake_result(self):
  result=web.format_results({"query":"NonexistentXYZ","results":[]})
  self.assertIn("Nebudu",result)
if __name__=='__main__':unittest.main()