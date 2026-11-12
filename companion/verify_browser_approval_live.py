"""Real Edge, two separately approved fields, same live task session; private fixture."""
import json,time,tempfile,threading,types
from pathlib import Path
from companion_store import Store
from companion_tools import build_registry
from companion_agent import Agent
import companion_settings as s

def run():
 with tempfile.TemporaryDirectory(prefix='browser-acceptance-',dir=s.ROOT) as tmp:
  root=Path(tmp);base=root/'BrainCore';base.mkdir();settings=types.SimpleNamespace(ROOT=root,BASE=base,ARTIFACTS=root/'artifacts',REPO=s.REPO,build_id=s.build_id)
  store=Store(base/'test.sqlite');cid=store.conversation('own-browser-fixture');store.submit(cid,'Vyplň obě pole vlastního zkušebního formuláře.');task=store.claim('qa',300)
  registry=build_registry(store,task,settings);original=registry.entries['browser_open']['function'];proof={};approved=[];stop=threading.Event()
  def fixture(url):
   original(url);registry.browser.page.set_content('<title>Own JARVIS fixture</title><label>First<input aria-label="First"></label><label>Second<input aria-label="Second"></label>')
   return registry.browser.snapshot()
  registry.entries['browser_open']['function']=fixture
  class Model:
   step=0
   def chat(self,messages,tools):
    self.step+=1
    if self.step==1:name='browser_open';args={'url':'https://example.com'}
    elif self.step in (2,3):
     snap=registry.browser.snapshot();label='First' if self.step==2 else 'Second';field=next(e for e in snap['elements'] if e['name']==label)
     name='browser_fill';args={'ref':field['ref'],'text':label+' value','document_id':snap['document_id'],'state_hash':snap['state_hash']}
    else:
     proof['first']=registry.browser.page.get_by_label('First').input_value();proof['second']=registry.browser.page.get_by_label('Second').input_value();return {'content':'Obě pole byla vyplněna.'}
    return {'content':'','tool_calls':[{'id':'step'+str(self.step),'function':{'name':name,'arguments':args}}]}
  def approvals():
   while not stop.wait(.05):
    t=store.get(task['id'])
    if t['status']=='WAITING_APPROVAL':
     approved.append(t['pending']);store.approve(task['id']);store.activate_approved(task['id'],task['owner'])
  thread=threading.Thread(target=approvals,daemon=True);thread.start()
  try:Agent(store,registry,Model(),task,hold_approvals=True).run()
  finally:stop.set();thread.join(2)
  result={'approvals':len(approved),'field_values':proof,'status':store.get(task['id'])['status'],'fixture_only':True}
  print(json.dumps(result),flush=True)
  assert len(approved)==2 and proof=={'first':'First value','second':'Second value'} and result['status']=='VERIFIED'
if __name__=='__main__':run()
