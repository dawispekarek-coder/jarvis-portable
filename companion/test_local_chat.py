import io,json,unittest
from unittest.mock import patch
from local_chat import extract_request,answer_local,LocalModelUnavailable,ENDPOINT
class LocalChatTests(unittest.TestCase):
 def test_opt_in(self):
  self.assertEqual(extract_request('/local Ahoj'),'Ahoj')
  self.assertEqual(extract_request('Lokálně: Ahoj'),'Ahoj')
  self.assertIsNone(extract_request('Oprav ForeverRoute'))
 def test_bounds(self):
  with self.assertRaises(ValueError):answer_local('')
  with self.assertRaises(ValueError):answer_local('X'*701)
 def test_local_api_no_tools(self):
  rsp=io.BytesIO(json.dumps({'message':{'content':'Ahoj'}}).encode())
  with patch('local_chat.urllib.request.urlopen',return_value=rsp) as mock:
   self.assertEqual(answer_local('Pozdrav'),'Ahoj')
  req=mock.call_args.args[0]
  self.assertEqual(req.full_url,ENDPOINT)
  data=json.loads(req.data)
  self.assertFalse(data['stream'])
  self.assertFalse(data['think'])
  self.assertIn('Nemáš internet',data['messages'][0]['content'])
 def test_empty_response_is_failure(self):
  rsp=io.BytesIO(json.dumps({'message':{'content':''}}).encode())
  with patch('local_chat.urllib.request.urlopen',return_value=rsp):
   with self.assertRaises(LocalModelUnavailable):answer_local('Ahoj')
 def test_offline_is_failure(self):
  with patch('local_chat.urllib.request.urlopen',side_effect=OSError('offline')):
   with self.assertRaises(LocalModelUnavailable):answer_local('Ahoj')
if __name__=='__main__':unittest.main()