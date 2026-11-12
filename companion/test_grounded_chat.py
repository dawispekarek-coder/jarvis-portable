"""Offline regression for source-grounded, no-tools local conversation."""
import io,json,unittest
from unittest.mock import patch
import grounded_chat as gc
HITS=[{'source':'ForeverRoute/docs/planner.md','line':42,'title':'Planner V4',
       'excerpt':'Planner V4 je samostatný offline plánovač, žádné externí AI.'}]
class GroundedTest(unittest.TestCase):
 def test_opt_in_only(self):
  self.assertEqual(gc.extract_request('Zeptej se znalostí: Planner V4'),('answer','Planner V4'))
  self.assertEqual(gc.extract_request('Plán ze znalostí: Planner V4'),('plan','Planner V4'))
  self.assertIsNone(gc.extract_request('Oprav Lua'))
 def test_no_evidence_never_calls_model(self):
  with patch('grounded_chat.retrieve',return_value=[]),patch('grounded_chat.urllib.request.urlopen') as call:
   r=gc.answer_grounded('nonsensical query')
   self.assertEqual(r['status'],'NO_EVIDENCE')
   call.assert_not_called()
 def test_cited_answer_and_local_only(self):
  response=io.BytesIO(json.dumps({'message':{'content':'Planner funguje offline.'}}).encode())
  with patch('grounded_chat.retrieve',return_value=HITS),patch('grounded_chat.urllib.request.urlopen',return_value=response) as call:
   r=gc.answer_grounded('Planner V4')
  self.assertEqual(r['status'],'MODEL_ANSWER_UNVERIFIED')
  self.assertIn('ForeverRoute/docs/planner.md:42',r['reply'])
  req=call.call_args.args[0]
  self.assertEqual(req.full_url,'http://127.0.0.1:11434/api/chat')
  body=json.loads(req.data)
  self.assertFalse(body['think'])
  self.assertFalse(body['stream'])
  self.assertIn('NEDŮVĚRYHODNÉ',body['messages'][0]['content'])
 def test_offline_shows_sources(self):
  with patch('grounded_chat.retrieve',return_value=HITS),patch('grounded_chat.urllib.request.urlopen',side_effect=OSError('offline')):
   r=gc.answer_grounded('Planner V4')
  self.assertEqual(r['status'],'MODEL_UNAVAILABLE')
  self.assertIn('ForeverRoute/docs/planner.md:42',r['reply'])
 def test_secrets_redacted_even_in_untrusted_docs(self):
  hit={**HITS[0],'excerpt':'Bearer superSensitiveTokenXYZ and a nice planner.'}
  system,prompt=gc.build_prompt('Planner V4',[hit],'answer')
  self.assertNotIn('superSensitiveTokenXYZ',prompt)
  self.assertIn('NEDŮVĚRYHODNÉ',system)
 def test_plan_not_done(self):
  result=io.BytesIO(json.dumps({'message':{'content':'Navrhuji test.'}}).encode())
  with patch('grounded_chat.retrieve',return_value=HITS),patch('grounded_chat.urllib.request.urlopen',return_value=result):
   r=gc.answer_grounded('Planner','plan')
  self.assertIn('nic jsem neprovedl',r['reply'])
if __name__=='__main__':unittest.main()