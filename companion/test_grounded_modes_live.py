import asyncio,json,websockets,sys
port=7358
async def send(ws,text):
 await ws.send(json.dumps({'type':'chat','text':text},ensure_ascii=False))
 answer=[];events=[]
 for _ in range(30):
  e=json.loads(await asyncio.wait_for(ws.recv(),80))
  events.append(e['type'])
  if e['type']=='assistant':answer.append(e.get('text',''))
  if e['type']=='done':break
 assert events[-1]=='done' and len(answer)==1,(text,events)
 return answer[0]
async def main():
 async with websockets.connect(f'ws://127.0.0.1:{port}/ws',origin='http://127.0.0.1:7353') as ws:
  await ws.recv()
  no=await send(ws,'Zeptej se znalostí: neexistujicifakt5839201')
  assert 'podklad' in no and 'vymýšlet' in no and 'Dohledané podklady:' not in no,no
  print('NO_EVIDENCE_PASS',flush=True)
  plan=await send(ws,'Plán ze znalostí: Jak otestovat Planner V4?')
  assert 'nic jsem neprovedl' in plan and 'ForeverRoute/' in plan,plan
  print('PROPOSE_ONLY_PASS',len(plan),flush=True)
if __name__=='__main__':
 port=int(sys.argv[1]) if len(sys.argv)>1 else 7358
 asyncio.run(main())