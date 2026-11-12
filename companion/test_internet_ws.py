"""Real V2 chat routes connectivity commands to OS/network tool, not local LLM."""
import asyncio,json,sys,urllib.request,websockets
async def ask(ws,prompt):
 await ws.send(json.dumps({'type':'chat','text':prompt},ensure_ascii=False))
 all_events=[]
 for i in range(18):
  msg=json.loads(await asyncio.wait_for(ws.recv(),45))
  all_events.append(msg)
  if msg.get('type')=='done':break
 replies=[e.get('text','') for e in all_events if e.get('type')=='assistant']
 assert len(replies)==1 and all_events[-1].get('type')=='done',all_events
 return replies[0],all_events
async def main(port):
 with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/tools',timeout=5) as rs:
  offered=json.load(rs)
 assert any(x.get('name')=='internet_connect_verified' for x in offered),offered
 async with websockets.connect(f'ws://127.0.0.1:{port}/ws',origin='http://127.0.0.1:7353') as ws:
  await asyncio.wait_for(ws.recv(),8)
  for prompt in ('napoj se na internet','Připoj se k internetu','zkontroluj internet'):
   answer,events=await ask(ws,prompt)
   assert 'Internet JE připojený a ověřený' in answer,(prompt,answer)
   assert 'https://www.python.org/' in answer,(prompt,answer)
   assert 'Lokální AI (bez internetu' not in answer,(prompt,answer)
   assert any('V2 internet: ONLINE' in e.get('text','') for e in events),(prompt,events)
   print('REAL_INTERNET_COMMAND_PASS',prompt,len(answer),flush=True)
if __name__=='__main__':
 asyncio.run(main(int(sys.argv[1]) if len(sys.argv)>1 else 7399))