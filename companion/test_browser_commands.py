import unittest
from browser_commands import intent,execute
class Tests(unittest.TestCase):
 def test_commands(self):
  self.assertEqual(intent("Otevři prohlížeč"),"prohlizec")
  self.assertEqual(intent("Jarvisi otevři Google"),"google")
  self.assertEqual(intent("Spusť YouTube"),"youtube")
 def test_reject(self):
  self.assertIsNone(intent("Otevři Google a smaž složku"))
  self.assertIsNone(intent("Otevři https://example.com"))
 def test_execution(self):
  calls=[]
  self.assertEqual(execute("github",lambda url,new=0:calls.append(url) or True)["status"],"REQUESTED")
  self.assertEqual(calls,["https://github.com/"])
  self.assertEqual(execute("google",lambda *a,**k:False)["status"],"FAILED")
  self.assertEqual(execute("unknown")["status"],"REFUSED")
if __name__=="__main__":unittest.main()
