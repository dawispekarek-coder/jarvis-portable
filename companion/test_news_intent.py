import unittest
from behavior_router import extract_web_intent
class NewsIntentTests(unittest.TestCase):
 def test_news(self):
  for query in ["shrň mi dnešní zprávy","Shrň dnešní zprávy","přehled aktuálních zpráv","nejdi dnešní zprávy"]:
   if query.startswith("nejdi"):continue
   self.assertEqual(extract_web_intent(query),"dnesni aktualni zpravy")
 def test_subject(self):
  self.assertEqual(extract_web_intent("shrň mi dnešní zprávy o ekonomice"),"dnesni aktualni zpravy ekonomice")
 def test_local_excluded(self):
  self.assertIsNone(extract_web_intent("shrň mi dnešní zprávy v souboru"))
if __name__=="__main__":unittest.main()
