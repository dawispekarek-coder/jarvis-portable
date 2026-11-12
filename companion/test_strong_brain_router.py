"""No secret leakage, no paid route, strict truthfulness and fallback."""
import json,subprocess,unittest
from unittest.mock import patch
import strong_brain_router as router

class StrongBrainTests(unittest.TestCase):
 def test_explicit_opt_in_only(self):
  self.assertEqual(router.extract('Silnější AI: Jak funguje Lua?'),'Jak funguje Lua?')
  self.assertIsNone(router.extract('Oprav addon'))
 def test_secret_never_sent(self):
  with patch('strong_brain_router.subprocess.run') as call:
   result=router.free_cloud('password=superlongsecret')
  self.assertEqual(result['status'],'SENSITIVE_TEXT_REJECTED')
  call.assert_not_called()
 def test_mojibake_rejected(self):
  self.assertFalse(router.cloud_quality('ĂÄ Ĺ â€ Ă'))
  self.assertTrue(router.cloud_quality('Lua 5.1 uses pattern classes.'))
 def test_hosted_success_labeled_unverified(self):
  response={'status':'MODEL_RESPONSE','result_exit':0,'answer':'Lua uses %p for punctuation.'}
  mock=subprocess.CompletedProcess([],0,json.dumps(response),'')
  with patch('strong_brain_router.subprocess.run',return_value=mock):
   result=router.free_cloud('Lua punctuation')
  self.assertEqual(result['status'],'HOSTED_UNVERIFIED')
 def test_bad_cloud_falls_back(self):
  with patch('strong_brain_router.free_cloud',return_value={'status':'HOSTED_QUALITY_REJECTED','answer':''}),patch('strong_brain_router.generate',return_value={'reply':'Lokální odpověď'}):
   out=router.answer('Jak funguje Lua?')
  self.assertEqual(out['status'],'LOCAL_FALLBACK')
  self.assertIn('Lokální odpověď',out['reply'])
 def test_never_fake_execution(self):
  with patch('strong_brain_router.free_cloud') as invoke:
   out=router.answer('Spusť program')
  self.assertEqual(out['status'],'NO_TOOL_ACCESS')
  invoke.assert_not_called()

if __name__=='__main__':unittest.main()