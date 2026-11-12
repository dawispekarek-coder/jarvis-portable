"""End to end acceptance on the installed local companion; only private test files."""
import asyncio,json,time,uuid,urllib.request,subprocess,sys
from pathlib import Path
import websockets
import companion_settings as s
BASE='http://127.0.0.1:7430';CLIENT='acceptance-'+uuid.uuid4().hex
out=s.ROOT/'reports'/'companion_live';out.mkdir(parents=True,exist_ok=True)
def req(path,body=None):
 r=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={'X-Jarvis-Client':CLIENT,'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=8) as f:return json.load(f)
async def done(tid,limit=180):
 deadline=time.time()+limit
 while time.time()<deadline:
  task=await asyncio.to_thread(req,'/companion/tasks/'+tid)
  if task['status'] not in ('QUEUED','RUNNING'):return task
  await asyncio.sleep(.6)
 raise RuntimeError('task_timeout:'+tid)
async def main():
 result={'build':req('/health')['build'],'client':CLIENT}
 name='acceptance_'+uuid.uuid4().hex[:8]+'.md';goal=f'Vytvoř soubor {name} s přesným obsahem: Ahoj Davide.'
 async with websockets.connect('ws://127.0.0.1:7430/ws?client='+CLIENT) as ws:
  await ws.send(json.dumps({'type':'chat','text':goal,'request_id':'disconnect-case'}))
  while True:
   event=json.loads(await ws.recv())
   if event['type']=='accepted':tid=event['task_id'];break
 result['websocket_accepted']=tid
 result['duplicate_request_same_task']=req('/companion/tasks',{'goal':goal,'request_id':'disconnect-case'})['id']==tid
 # Restart the web/API process while its independent worker continues the task.
 owner=req('/health')['worker']['owner'];token=(s.BASE/'companion_control.key').read_text().strip()
 r=urllib.request.Request(BASE+'/companion/reload',data=b'',headers={'X-Jarvis-Control':token})
 with urllib.request.urlopen(r,timeout=5) as f:json.load(f)
 await asyncio.sleep(.8)
 subprocess.Popen([sys.executable,str(s.ROOT/'launch_companion.pyw'),'--background'],cwd=s.ROOT)
 for _ in range(70):
  try:
   health=await asyncio.to_thread(req,'/health')
   if health['build']==s.build_id():break
  except Exception:pass
  await asyncio.sleep(.3)
 else:raise RuntimeError('api_restart_timeout')
 result['api_restarted_worker_unchanged']=health['worker']['owner']==owner
 task=await done(tid);result['disconnected_task_status']=task['status']
 files=req('/companion/tasks/'+tid+'/artifacts')['files'];result['files']=files
 p=s.ARTIFACTS/tid/name
 result['artifact_exact']=p.is_file() and p.read_text(encoding='utf-8').strip()=='Ahoj Davide.'
 state=req('/companion/state');result['history_after_restart']=any(m['task_id']==tid and m['role']=='assistant' for m in state['history'])
 async with websockets.connect('ws://127.0.0.1:7430/ws?client='+CLIENT) as ws:
  for _ in range(12):
   message=json.loads(await asyncio.wait_for(ws.recv(),5))
   if message.get('type')=='assistant' and message.get('task_id')==tid:result['websocket_history_replayed']=True;break
 # An accepted task can be stopped without killing an unrelated worker/service.
 stopped=req('/companion/tasks',{'goal':'Vysvětli krátce účel této zkoušky.','request_id':'stop-case'})
 req('/companion/tasks/'+stopped['id']+'/cancel',{})
 await asyncio.sleep(.5);result['stop_status']=req('/companion/tasks/'+stopped['id'])['status']
 result['worker_alive_after_stop']=req('/health')['worker']['alive']
 (out/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=True),flush=True)
 assert all(result[k] for k in ('duplicate_request_same_task','api_restarted_worker_unchanged','artifact_exact','history_after_restart','websocket_history_replayed','worker_alive_after_stop'))
 assert result['disconnected_task_status']=='VERIFIED' and result['stop_status']=='CANCELLED'
if __name__=='__main__':asyncio.run(main())
