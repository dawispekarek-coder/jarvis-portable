import asyncio,json,sys,websockets
from project_tools import status
async def main(port):
 before=status()
 async with websockets.connect(f'ws://127.0.0.1:{port}/ws',origin='http://127.0.0.1:7353') as ws:
  greeting=json.loads(await asyncio.wait_for(ws.recv(),5))
  assert greeting['type']=='info'
  await ws.send(json.dumps({'type':'chat','text':'Prověř chyby ForeverRoute v Lua funkci FR_NowNavRepeatsTitle'},ensure_ascii=False))
  events=[]
  for i in range(20):
   e=json.loads(await asyncio.wait_for(ws.recv(),45))
   events.append(e)
   if e['type']=='done':break
  replies=[e.get('text','') for e in events if e['type']=='assistant']
  assert len(replies)==1 and events[-1]['type']=='done',events
  reply=replies[0]
  assert 'POUZE ČTECÍ' in reply,reply
  assert 'FR_NowNavRepeatsTitle' in reply,reply
  assert '72 kontrol, 3 chyb' in reply,reply
  assert 'Oprava ani zápis' in reply,reply
  assert any('LangGraph' in e.get('text','') for e in events),events
  print('AUTO_INSPECTION_WS_PASS',','.join(e['type'] for e in events),len(reply),flush=True)
 after=status()
 assert before['commit']==after['commit'] and before['changed_count']==after['changed_count']
 print('PRODUCTION_REPO_UNCHANGED_PASS',flush=True)
if __name__=='__main__':asyncio.run(main(int(sys.argv[1]) if len(sys.argv)>1 else 7362))