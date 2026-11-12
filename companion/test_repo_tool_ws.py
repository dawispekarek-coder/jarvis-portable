"""Real V2 UI protocol: an actual read-only Git inspection, not an AI guess."""
import asyncio,json,sys,urllib.request,websockets
import project_tools
async def run(port):
 before=project_tools.status()
 req=urllib.request.Request(f'http://127.0.0.1:{port}/api/tools')
 with urllib.request.urlopen(req,timeout=5) as response:
  listed=json.load(response)
 assert any(x['name']=='foreverroute_git_status' for x in listed)
 async with websockets.connect(f'ws://127.0.0.1:{port}/ws',origin='http://127.0.0.1:7353') as ws:
  banner=json.loads(await asyncio.wait_for(ws.recv(),6))
  assert banner['type']=='info'
  await ws.send(json.dumps({'type':'chat','text':'Zkontroluj Git ForeverRoute'},ensure_ascii=False))
  events=[]
  for _ in range(14):
   event=json.loads(await asyncio.wait_for(ws.recv(),9))
   events.append(event)
   if event['type']=='done':break
  texts=[x.get('text','') for x in events if x['type']=='assistant']
  assert len(texts)==1 and events[-1]['type']=='done',events
  reply=texts[0]
  assert 'Skutečná kontrola Gitu' in reply and before['commit'] in reply,reply
  assert before['branch'] in reply,reply
  assert any('foreverroute_git_status' in x.get('text','') for x in events if x['type']=='info'),events
  print('REAL_GIT_STATUS_WS_PASS',before['branch'],before['commit'],flush=True)
 after=project_tools.status()
 assert before['commit']==after['commit'] and before['changed_count']==after['changed_count']
 print('SOURCE_UNCHANGED_PASS',flush=True)
if __name__=='__main__':asyncio.run(run(int(sys.argv[1]) if len(sys.argv)>1 else 7360))