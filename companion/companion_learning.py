"""Exercise the serving registry, persist scoped recipes, invalidate them on build changes."""
import json,time,uuid,tempfile,types
from pathlib import Path
from tool_learning import _connect,current,STATUSES

def train_registry(registry,settings,report=None,exercises=None):
 build=settings.build_id();path=settings.BASE/'tool_skills.sqlite';run_id=uuid.uuid4().hex;catalog=registry.catalog();results=[]
 with _connect(path) as db:
  db.execute("UPDATE runs SET status='INTERRUPTED',finished=? WHERE status='RUNNING'",(time.time(),))
  db.execute('INSERT INTO runs(id,started,status,discovered) VALUES(?,?,?,?)',(run_id,time.time(),'RUNNING',len(catalog)));db.commit()
  for i,entry in enumerate(catalog,1):
   name=entry['name'];proof={};lesson=entry['description'];status_name='UNTESTED'
   if report:report({'index':i,'total':len(catalog),'name':name,'phase':'testing'})
   if not entry['available']:status_name='UNAVAILABLE'
   elif exercises and name in exercises:
    try:
     result=exercises[name]();proof={'real_exercise':True,'ok':bool(result.get('ok')),'scope':result.get('value',{}).get('scope','bounded tool exercise')}
     status_name='VERIFIED' if result.get('ok') else 'FAILED'
     v=result.get('value',{})
     if v.get('failure_count',0) or v.get('behavior_verified') is False:status_name='LIMITED'
    except Exception as exc:status_name='FAILED';proof={'error':type(exc).__name__}
   elif entry['approval']:status_name='NEEDS_APPROVAL';lesson+=' Praktická změna vyžaduje konkrétní schválenou stránku a akci.'
   elif name in ('learn_tools','web_research','image_search'):status_name='READY';lesson+=' Rozhraní je připojené; celý scénář se v této zkoušce neopakoval.'
   key='runtime:'+name;example=name+' '+json.dumps(registry.entries[name]['parameters'].get('properties',{}),ensure_ascii=False)[:220]
   db.execute('INSERT INTO skills VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,status=excluded.status,example=excluded.example,lesson=excluded.lesson,evidence=excluded.evidence,source_hash=excluded.source_hash,updated=excluded.updated,run_id=excluded.run_id',(key,name,status_name,example,lesson,json.dumps(proof),build,time.time(),run_id))
   db.execute('UPDATE runs SET checked=? WHERE id=?',(i,run_id));db.commit();results.append({'id':key,'name':name,'status':status_name})
  db.execute("UPDATE runs SET status='COMPLETED',finished=? WHERE id=?",(time.time(),run_id))
 return {'status':'COMPLETED','run_id':run_id,'checked':len(results),'counts':{s:sum(x['status']==s for x in results) for s in STATUSES},'results':results,'scope':'Each result states the actual tested scope; READY is not full execution.'}

def status(settings):
 state=current(settings.BASE/'tool_skills.sqlite');build=settings.build_id()
 with _connect(settings.BASE/'tool_skills.sqlite') as db:hashes=dict(db.execute("SELECT id,source_hash FROM skills WHERE id LIKE 'runtime:%'"))
 state['skills']=[{**s,'status':s['status'] if hashes.get(s['id'])==build else 'STALE','source_changed_since_test':hashes.get(s['id'])!=build} for s in state['skills'] if s['id'].startswith('runtime:')]
 return state

def skill_context(settings):
 state=status(settings);known=[s['name']+'='+s['status']+': '+s['lesson'][:100] for s in state['skills'] if s['status'] in ('VERIFIED','READY')]
 return 'Ověřené místní postupy: '+'; '.join(known)[:1600] if known else 'Pro tento build zatím nejsou aktuální ověřené postupy.'

def exercise_runtime(registry,store,task,settings,report=None):
 from companion_tools import build_registry,configure_legacy
 from companion_store import Store
 with tempfile.TemporaryDirectory(prefix='skill-exercises-',dir=settings.ROOT) as tmp:
  root=Path(tmp);base=root/'BrainCore';base.mkdir();repo=root/'repo';repo.mkdir();(repo/'test.lua').write_text('return 1\n',encoding='utf-8')
  fixture_settings=types.SimpleNamespace(ROOT=root,BASE=base,ARTIFACTS=root/'artifacts',REPO=repo,build_id=settings.build_id)
  fixture_store=Store(base/'fixture.sqlite');cid=fixture_store.conversation('training-only');fake=fixture_store.submit(cid,'Zapamatuj si test a naplánuj zkoušku');fixture=build_registry(fixture_store,fake,fixture_settings)
  configure_legacy(settings)
  safe_args={'calculate':{'expression':'2+2'},'project_status':{},'project_search':{'symbol':'FR_NowNavRepeatsTitle'},'project_study':{'goal':'ForeverRoute'},'project_read':{'path':'README.md'},'knowledge_search':{'query':'ForeverRoute'},'web_search':{'query':'Python official documentation'},'web_read':{'url':'https://docs.python.org/3/'},'voice_status':{},'internet_status':{},'capability_status':{},'list_schedules':{},'learning_status':{}}
  exercises={name:(lambda name=name,args=args:registry.execute(name,args)) for name,args in safe_args.items() if name in registry.entries}
  fixture_args={'memory_save':{'key':'exercise','value':'Fixture only'},'memory_search':{'query':'exercise'},'memory_forget':{'key':'exercise'},'artifact_write':{'name':'exercise.md','content':'Ověřený postup\n'},'code_propose':{'path':'test.lua','old':'return 1','new':'return 2'},'learn_czech':{}}
  for name,args in fixture_args.items():
   if name in registry.entries:exercises[name]=lambda name=name,args=args:fixture.execute(name,args)
  def scheduling():
   scheduled=fixture.execute('schedule_task',{'goal':'fixture','delay_seconds':300,'interval_seconds':0});fixture.execute('pause_schedule',{'id':scheduled['value']['id']});return scheduled
  exercises['schedule_task']=scheduling
  def pause():
   s=fixture_store.schedule(cid,'fixture',time.time()+300);return fixture.execute('pause_schedule',{'id':s['id']})
  exercises['pause_schedule']=pause
  if getattr(registry,'browser',None) and registry.browser.available:exercises['browser_open']=lambda:registry.execute('browser_open',{'url':'https://example.com'})
  if getattr(registry,'desktop',None) and registry.desktop.available:exercises['desktop_observe']=lambda:registry.execute('desktop_observe',{})
  exercises['voice_speak']=lambda:fixture.execute('voice_speak',{'text':'Toto je zkouška hlasu Jarvis.'})
  try:return train_registry(registry,settings,report,exercises)
  finally:fixture.browser.close();configure_legacy(settings)
