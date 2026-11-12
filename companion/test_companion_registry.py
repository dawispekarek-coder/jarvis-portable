import tempfile,unittest
from pathlib import Path
try:
 from companion_registry import Registry,ToolError
 from companion_tools import confined,write_artifact,read_project
except ImportError:
 Registry=None

class RegistryTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(Registry,'Typed tool registry is missing')
 def test_bad_arguments_never_reach_tool(self):
  r=Registry();observed=[]
  r.add('read','Read',{'type':'object','properties':{'count':{'type':'integer','minimum':1,'maximum':5}},'required':['count'],'additionalProperties':False},lambda count:observed.append(count),verifier=lambda v:True)
  for args in ({'count':True},{'count':0},{'count':2,'shell':'calc'},{'count':'2'}):
   with self.assertRaises(ToolError):r.validate('read',args)
  self.assertEqual(observed,[])
 def test_success_requires_verification(self):
  r=Registry();r.add('read','Read',{'type':'object','properties':{},'additionalProperties':False},lambda:{'claimed':'done'},verifier=lambda v:False)
  self.assertFalse(r.execute('read',{})['ok'])
 def test_catalog_is_model_schema_source(self):
  r=Registry();r.add('read','Read',{'type':'object','properties':{},'additionalProperties':False},lambda:1,verifier=lambda v:v==1)
  self.assertEqual(r.schemas()[0]['function']['name'],r.catalog()[0]['name'])
 def test_private_artifact_is_written_and_can_be_read_back(self):
  with tempfile.TemporaryDirectory() as tmp:
   result=write_artifact(Path(tmp),'note.md','Ahoj světe\nDruhý řádek\n')
   self.assertEqual(Path(result['path']).read_bytes(),'Ahoj světe\nDruhý řádek\n'.encode('utf-8'))
   self.assertTrue(result['verified'])
 def test_path_escape_and_secret_project_read_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'DB').mkdir();(root/'DB'/'quests.lua').write_text('data')
   (root/'secret.env').write_text('hidden');(root/'code.lua').write_text('return 1')
   for bad in ('../outside','/etc/passwd','DB/quests.lua','secret.env'):
    with self.assertRaises(ToolError):read_project(root,bad)
   self.assertEqual(read_project(root,'code.lua')['text'],'return 1')

if __name__=='__main__':unittest.main()
