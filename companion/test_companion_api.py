import unittest,tempfile
from pathlib import Path
try:
 from companion_api import create_app
except ImportError:create_app=None

class ApiTests(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(create_app,'Companion UI integration is missing')
  from fastapi.testclient import TestClient
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'OriginalJarvisUI').mkdir()
  (self.root/'OriginalJarvisUI'/'index.html').write_text('<html><head></head><body><div id="root"></div></body></html>')
  self.app=create_app(self.root,start_worker=False);self.client=TestClient(self.app,base_url='http://127.0.0.1:7430');self.key='desktop-test-client';self.headers={'X-Jarvis-Client':self.key}
 def tearDown(self):
  if hasattr(self,'client'):self.client.close();self.tmp.cleanup()
 def test_cross_origin_mutation_is_blocked(self):
  r=self.client.post('/companion/tasks',json={'goal':'Test'},headers={**self.headers,'Origin':'https://evil.example'})
  self.assertEqual(r.status_code,403)
 def test_untrusted_host_is_blocked(self):
  r=self.client.get('/api/health',headers={'Host':'attacker.example:7430'})
  self.assertEqual(r.status_code,403)
 def test_service_reload_requires_private_local_launcher_token(self):
  self.assertEqual(self.client.post('/companion/reload',headers=self.headers).status_code,403)
 def test_idempotent_tasks_and_private_conversations(self):
  a=self.client.post('/companion/tasks',json={'goal':'Zkontroluj Git','request_id':'same'},headers=self.headers).json()
  b=self.client.post('/companion/tasks',json={'goal':'Zkontroluj Git','request_id':'same'},headers=self.headers).json()
  self.assertEqual(a['id'],b['id'])
  other=self.client.get('/companion/tasks/'+a['id'],headers={'X-Jarvis-Client':'someone-else'})
  self.assertEqual(other.status_code,404)
 def test_disconnect_does_not_cancel_accepted_work(self):
  with self.client.websocket_connect('ws://127.0.0.1:7430/ws?client='+self.key,headers={'Origin':'http://127.0.0.1:7430'}) as ws:
   ws.receive_json();ws.send_json({'type':'chat','text':'Nauč se pracovat se svými nástroji','request_id':'ws-one'})
   for _ in range(8):
    msg=ws.receive_json()
    if msg.get('type')=='accepted':break
  state=self.client.get('/companion/state',headers=self.headers).json()
  self.assertEqual(len(state['tasks']),1);self.assertEqual(state['tasks'][0]['status'],'QUEUED')
 def test_registry_and_build_are_actual_service_identity(self):
  health=self.client.get('/api/health').json();tools=self.client.get('/api/tools').json()
  self.assertIn('build',health);self.assertTrue(any(t['name']=='learn_tools' for t in tools))
 def test_original_ui_has_companion_controls(self):
  page=self.client.get('/').text;self.assertIn('/companion-ui.js',page)

if __name__=='__main__':unittest.main()
