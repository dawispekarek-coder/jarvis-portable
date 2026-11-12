import asyncio,json,sys,websockets
async def run(port):
 async with websockets.connect(f'ws://127.0.0.1:{port}/ws',origin='http://127.0.0.1:7353') as ws:
  await asyncio.wait_for(ws.recv(),8)
  await ws.send(json.dumps({'type':'chat','text':'Lokálně: Kolik je sedm krát osm?'},ensure_ascii=False))
  events=[]
  for _ in range(20):
   e=json.loads(await asyncio.wait_for(ws.recv(),80))
   events.append(e)
   if e.get('type')=='done':break
  else:raise AssertionError('MISSING_DONE')
  replies=[x['text'] for x in events if x.get('type')=='assistant']
  assert len(replies)==1,replies
  assert 'Experimentální lokální model' in replies[0],replies
  assert '56' in replies[0],replies
  print('LIVE_LOCAL_CHAT_PASS',','.join(x['type'] for x in events),len(replies[0]),flush=True)
if __name__=='__main__':asyncio.run(run(int(sys.argv[1]) if len(sys.argv)>1 else 7356))