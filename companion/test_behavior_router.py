import unittest
import behavior_router as r

class IntentRules(unittest.TestCase):
 def test_search_words_trigger_actual_web(self):
  cases={'Najdi Lua 5.1 manual':'Lua 5.1 manual',
         'Najdi mi informace o Pythonu':'informace o Pythonu',
         'Dohledej nové verze LangGraph':'nové verze LangGraph',
         'Vyhledej co je Lua':'co je Lua',
         'Hledej návody k Lua':'návody k Lua'}
  for text,expected in cases.items():
   with self.subTest(text=text):self.assertEqual(r.extract_web_intent(text),expected)
 def test_local_requests_do_not_leak_to_web(self):
  for text in ('Najdi v souborech heslo','Najdi na disku projekt',
               'Najdi v dokumentaci Planner V4','Najdi v kódu FR_NowNavRepeatsTitle'):
   with self.subTest(text=text):self.assertIsNone(r.extract_web_intent(text))
 def test_plain_chat_not_searched(self):
  for text in ('Ahoj','Jak se máš?','Oprav ForeverRoute','Kolik je dva plus dva?'):
   self.assertIsNone(r.extract_web_intent(text))
 def test_empty_search_explicit(self):
  self.assertEqual(r.extract_web_intent('Najdi'),'')
 def test_long_or_invalid(self):
  self.assertIsNone(r.extract_web_intent('Najdi '+('x'*810)))
  self.assertIsNone(r.extract_web_intent(None))
if __name__=='__main__':unittest.main()