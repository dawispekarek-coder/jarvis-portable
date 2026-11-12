import io,json,unittest
from unittest.mock import patch
import general_brain as brain
class Notes:
 def search(self,q,limit=2):return [{'content':'ForeverRoute je naše testovací aplikace.'}]
class BrainTests(unittest.TestCase):
 def test_action_guard(self):
  self.assertTrue(brain.unconnected_action('Najdi obrázky kačiček'))
  self.assertTrue(brain.unconnected_action('Nainstaluj aplikaci'))
  self.assertFalse(brain.unconnected_action('Jak se máš?'))
 def test_default_model_without_prefix(self):
  response=io.BytesIO(json.dumps({'message':{'content':'Ahoj!'}}).encode())
  with patch('general_brain.urllib.request.urlopen',return_value=response) as call:
   x=brain.generate('Ahoj')
  self.assertIn('Ahoj',x['reply'])
  req=json.loads(call.call_args.args[0].data)
  self.assertEqual(req['messages'][-1]['content'],'Ahoj')
  self.assertNotIn('tools',req)
 def test_project_question_is_not_note_recall(self):
  from knowledge_store import handle_command
  self.assertIsNone(handle_command(Notes(),'Co víš o ForeverRoute?'))
 def test_failure_honest(self):
  with patch('general_brain.urllib.request.urlopen',side_effect=OSError('offline')):
   with self.assertRaises(brain.LocalModelUnavailable):brain.generate('Ahoj')
 def test_tool_call_not_exposed(self):
  response=io.BytesIO(json.dumps({'message':{'content':'<tool_call> hi'}}).encode())
  with patch('general_brain.urllib.request.urlopen',return_value=response):
   with self.assertRaises(brain.LocalModelUnavailable):brain.generate('Ahoj')
 def test_project_context_and_history(self):
  docs=[{'source':'ForeverRoute/README.md','line':5,'excerpt':'Planner V4 je systém plánování.'}]
  response=io.BytesIO(json.dumps({'message':{'content':'Planner je plánovač.'}}).encode())
  with patch('general_brain.knowledge.search',return_value=docs),patch('general_brain.urllib.request.urlopen',return_value=response) as mocked:
   x=brain.generate('Co víš o ForeverRoute Planneru?',[
    {'role':'user','content':'Zdravím'},
    {'role':'assistant','content':'Ahoj!'}],Notes())
  self.assertIn('ForeverRoute/README.md:5',x['reply'])
  req=json.loads(mocked.call_args.args[0].data)
  self.assertTrue(any('Uživatelská poznámka' in y['content'] for y in req['messages']))
  self.assertEqual(req['messages'][1]['content'],'Zdravím')
if __name__=='__main__':unittest.main()