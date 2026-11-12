import tempfile,unittest,types
from pathlib import Path
from companion_registry import Registry,obj
try:
 from companion_learning import train_registry,status
except ImportError:train_registry=None

class RuntimeLearningTests(unittest.TestCase):
 def test_learning_covers_actual_catalog_without_executing_unknown_writes(self):
  self.assertIsNotNone(train_registry,'Learning must use the actual runtime catalog')
  with tempfile.TemporaryDirectory() as tmp:
   r=Registry();called=[]
   r.add('calculate','Calculate',obj(),lambda:called.append('read') or {'result':4},verifier=lambda x:True)
   r.add('unknown_write','Write',obj(),lambda:called.append('write'),verifier=lambda x:True,write=True)
   settings=types.SimpleNamespace(BASE=Path(tmp),ROOT=Path(tmp),build_id=lambda:'build-1')
   result=train_registry(r,settings,exercises={'calculate':lambda:r.execute('calculate',{})})
   self.assertEqual(result['checked'],2);self.assertEqual(called,['read'])
   records={x['name']:x['status'] for x in result['results']};self.assertEqual(records['calculate'],'VERIFIED');self.assertEqual(records['unknown_write'],'UNTESTED')
   settings.build_id=lambda:'build-2'
   self.assertTrue(all(x['status']=='STALE' for x in status(settings)['skills']))
if __name__=='__main__':unittest.main()
