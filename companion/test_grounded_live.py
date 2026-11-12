"""Live original UI WebSocket proof that local AI receives cited KB context."""
import asyncio,json,sys,websockets
PORT=7358
async def main():
 async with websockets.connect(f'ws://127.0.0.1:{PORT}/ws',origin='http://127.0.0.1:7353') as ws:
  banner=json.loads(await asyncio.wait_for(ws.recv(),8))
  assert banner['type']=='info'
  await ws.send(json.dumps({'type':'chat','text':'Zeptej se znalostí: Jak funguje Planner V4?'}))
  events=[]
  while len(events)<25:
   e=json.loads(await asyncio.wait_for(ws.recv(),85))
   events.append(e)
   if e.get('type')=='done':break
  answers=[e.get('text','') for e in events if e.get('type')=='assistant']
  infos=[e.get('text','') for e in events if e.get('type')=='info']
  assert len(answers)==1 and events[-1]['type']=='done',(events,answers)
  result=answers[0]
  assert ('Dohledané podklady:' in result or 'Dohledané zdroje:' in result),result
  assert 'ForeverRoute/' in result,result
  print('GROUNDING_LIVE_PASS',json.dumps({'events':[e['type'] for e in events],'info':infos,'reply_sample':result[:450],'reply_len':len(result)},ensure_ascii=True),flush=True)
if __name__=='__main__':
 PORT=int(sys.argv[1]) if len(sys.argv)>1 else 7358
 asyncio.run(main())