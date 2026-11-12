import asyncio,json,sys,websockets
async def ask(ws,text):
 await ws.send(json.dumps({'type':'chat','text':text},ensure_ascii=False))
 events=[]
 for i in range(25):
  obj=json.loads(await asyncio.wait_for(ws.recv(),25))
  events.append(obj)
  if obj.get('type')=='done':break
 msgs=[e.get('text','') for e in events if e.get('type')=='assistant']
 assert len(msgs)==1 and events[-1]['type']=='done',events
 return msgs[0],events
async def main(port):
 async with websockets.connect(f'ws://127.0.0.1:{port}/ws',origin='http://127.0.0.1:7353') as ws:
  await asyncio.wait_for(ws.recv(),7)
  for prompt in ('máš přístup k forever route, zkus to znova, nastuduj si to','Co víš o ForeverRoute?'):
   msg,events=await ask(ws,prompt)
   assert 'ForeverRoute_PlannerV4.lua' in msg,msg
   assert 'ForeverRoute_QuestEngine.lua' in msg,msg
   assert 'ForeverRoute.toc:5' in msg,msg
   assert 'README.md:' in msg,msg
   assert 'Lokální AI (v této odpovědi' not in msg,msg
   assert any('Ověřená četba' in e.get('text','') for e in events),events
   print('REAL_PROJECT_STUDY_WS_PASS',prompt,len(msg),flush=True)
if __name__=='__main__':asyncio.run(main(int(sys.argv[1]) if len(sys.argv)>1 else 7398))
