"""Real UI WebSocket: default no-prefix model, project grounding, guarded actions."""
import asyncio,json,sys,websockets
async def ask(ws,text):
 await ws.send(json.dumps({'type':'chat','text':text},ensure_ascii=False))
 types=[];answers=[]
 for i in range(25):
  e=json.loads(await asyncio.wait_for(ws.recv(),85))
  types.append(e.get('type'))
  if e.get('type')=='assistant':answers.append(e.get('text',''))
  if e.get('type')=='done':break
 assert types[-1]=='done' and len(answers)==1,(text,types)
 return answers[0],types
async def run(port):
 async with websockets.connect(f'ws://127.0.0.1:{port}/ws',origin='http://127.0.0.1:7353') as ws:
  await asyncio.wait_for(ws.recv(),6)
  a,k=await ask(ws,'Ahoj Jarvisi, jak se máš?')
  assert 'Tuto funkci' not in a and 'Lokální AI' in a,a
  print('DEFAULT_CHAT_PASS',','.join(k),a[:130],flush=True)
  b,k=await ask(ws,'Co víš o ForeverRoute Planneru V4?')
  assert 'Tuto funkci' not in b and 'Místní podklady:' in b and 'ForeverRoute/' in b,b
  print('AUTO_PROJECT_KNOWLEDGE_PASS',','.join(k),len(b),flush=True)
  c,k=await ask(ws,'Najdi obrázky kačiček')
  assert 'zatím neumí' in c and 'Lokální AI' not in c,c
  print('NO_FAKE_ACTION_PASS',','.join(k),flush=True)
  d,k=await ask(ws,'A co jsi o tom projektu před chvílí říkal?')
  assert 'Tuto funkci' not in d and 'Lokální AI' in d,d
  print('SESSION_HISTORY_PASS',','.join(k),len(d),flush=True)
if __name__=='__main__':asyncio.run(run(int(sys.argv[1]) if len(sys.argv)>1 else 7359))