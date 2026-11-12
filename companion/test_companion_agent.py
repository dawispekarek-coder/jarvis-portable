import tempfile,unittest
from pathlib import Path
from companion_store import Store
from companion_registry import Registry,obj,text_schema
try:
 from companion_agent import Agent,goal_contract,known_call
except ImportError:
 Agent=None

class ScriptedModel:
 def __init__(self,answers):self.answers=iter(answers)
 def chat(self,messages,tools):return next(self.answers)
def call(name,args,id='c1'):return {'role':'assistant','content':'','tool_calls':[{'id':id,'function':{'name':name,'arguments':args}}]}

class AgentTests(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(Agent,'Tool-using agent loop is not implemented')
  self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'db');self.c=self.s.conversation('desktop');self.r=Registry()
 def tearDown(self):
  if hasattr(self,'tmp'):self.tmp.cleanup()
 def task(self,goal):
  t=self.s.submit(self.c,goal);return self.s.claim('test')
 def test_multiple_steps_execute_real_tools_before_verified_result(self):
  result=Path(self.tmp.name)/'result.txt'
  self.r.add('artifact_write','Write',obj({'name':text_schema(),'content':text_schema()}),lambda name,content:(result.write_text(content) or None) and {'path':str(result)},verifier=lambda v:result.read_text()=='Hotovo',write=True)
  model=ScriptedModel([call('artifact_write',{'name':'result.txt','content':'Hotovo'}),{'role':'assistant','content':'Soubor je uložený.'}])
  t=self.task('Vytvoř soubor result.txt');Agent(self.s,self.r,model,t).run()
  self.assertEqual(result.read_text(),'Hotovo');self.assertEqual(self.s.get(t['id'])['status'],'VERIFIED')
 def test_false_model_completion_without_tool_is_partial(self):
  t=self.task('Vytvoř soubor')
  Agent(self.s,self.r,ScriptedModel([{'role':'assistant','content':'Soubor jsem vytvořil.'}]*3),t).run()
  done=self.s.get(t['id']);self.assertEqual(done['status'],'PARTIAL');self.assertNotIn('Soubor jsem vytvořil.',done['answer'])
 def test_failed_tool_does_not_become_verified(self):
  self.r.add('read','Read',obj(),lambda:{'failed':True},verifier=lambda x:False)
  t=self.task('Najdi výsledek');Agent(self.s,self.r,ScriptedModel([call('read',{}),{'role':'assistant','content':'Hotovo'}]),t).run()
  self.assertEqual(self.s.get(t['id'])['status'],'PARTIAL')
 def test_approval_stops_action_and_resume_executes_once(self):
  result=[];self.r.add('save','Save',obj({'text':text_schema()}),lambda text:result.append(text) or {'saved':True},verifier=lambda x:x['saved'],write=True,approval=True)
  t=self.task('Ulož hodnotu');model=ScriptedModel([call('save',{'text':'A'})])
  Agent(self.s,self.r,model,t).run();self.assertEqual(result,[]);self.assertEqual(self.s.get(t['id'])['status'],'WAITING_APPROVAL')
  self.s.approve(t['id']);t=self.s.claim('test2')
  Agent(self.s,self.r,ScriptedModel([{'role':'assistant','content':'Uloženo.'}]),t).run()
  self.assertEqual(result,['A'])
 def test_questions_about_how_are_not_action_contracts(self):
  self.assertFalse(goal_contract('Jak vytvořit soubor?')['action'])
  self.assertTrue(goal_contract('Můžeš vytvořit soubor prosím?')['action'])
 def test_future_reminder_is_not_intercepted_as_memory_recall(self):
  route=known_call('Připomeň mi za deset minut kontrolu Gitu',{'memory_search','schedule_task'})
  self.assertNotEqual(route.get('name') if route else None,'memory_search')
 def test_connect_request_requires_connect_tool_not_only_status(self):
  self.assertIn('internet_connect',goal_contract('Připoj se na internet')['required'])
 def test_checkpoint_prevents_repeating_completed_write(self):
  count=[];self.r.add('save','Save',obj(),lambda:count.append(1) or {'saved':True},verifier=lambda x:True,write=True)
  t=self.task('Ulož hodnotu');self.s.begin_tool(t['id'],'c1','save',{},True);self.s.complete_tool(t['id'],'c1',{'ok':True,'verified':True,'value':{'saved':True},'tool':'save'})
  self.s.checkpoint(t['id'],{'messages':[{'role':'user','content':'Ulož hodnotu'}],'pending':[{'id':'c1','name':'save','arguments':{}}],'steps':1,'had_tools':False,'failed_tools':False})
  Agent(self.s,self.r,ScriptedModel([{'role':'assistant','content':'Uloženo.'}]),self.s.get(t['id'])).run();self.assertEqual(count,[])
 def test_claimed_goal_remains_authoritative_after_later_queued_messages(self):
  t=self.task('První cíl: '+'A'*2500)
  self.s.submit(self.c,'Druhý cíl')
  captured=[]
  class Model:
   def chat(self,messages,tools):captured.extend(messages);return {'content':'Rozumím prvnímu cíli.'}
  Agent(self.s,self.r,Model(),t).run()
  users=[x['content'] for x in captured if x['role']=='user']
  self.assertEqual(users[-1],t['goal']);self.assertFalse(any('Druhý cíl' in x for x in users))
 def test_unrelated_calculation_does_not_verify_scheduled_reminder(self):
  self.r.add('calculate','Calculate',obj(),lambda:{'result':4},verifier=lambda x:True)
  t=self.task('Připomeň mi za deset minut kontrolu Gitu')
  Agent(self.s,self.r,ScriptedModel([call('calculate',{}),{'content':'Připomínka je naplánovaná.'}]),t).run()
  done=self.s.get(t['id']);self.assertEqual(done['status'],'PARTIAL');self.assertNotIn('Připomínka je naplánovaná.',done['answer'])
 def test_failed_code_proposal_is_not_announced_as_created(self):
  self.r.add('code_propose','Code',obj(),lambda:{'failed':True},verifier=lambda x:False,write=True)
  t=self.task('Oprav ForeverRoute Lua')
  Agent(self.s,self.r,ScriptedModel([call('code_propose',{}),{'content':'Návrh je hotový.'}]),t).run()
  done=self.s.get(t['id']);self.assertEqual(done['status'],'PARTIAL');self.assertNotIn('Připravil jsem návrh kódu',done['answer'])

if __name__=='__main__':unittest.main()
