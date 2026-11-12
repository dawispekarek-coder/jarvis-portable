"""End-to-end real source search via original V2 WebSocket protocol."""
import asyncio,json,sys,websockets,urllib.request
import project_tools
async def ask(ws,text):
 await ws.send(json.dumps({'type':'chat','text':text},ensure_ascii=False))
 events=[]
 for _ in range(14):
  event=json.loads(await asyncio.wait_for(ws.recv(),10))
  events.append(event)
  if event['type']=='done':break
 replies=[e.get('text','') for e in events if e['type']=='assistant']
 assert len(replies)==1 and events[-1]['type']=='done',events
 return replies[0],events
async def main(port):
 with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/tools',timeout=5) as r:
  tools=json.load(r)
 assert any(x['name']=='foreverroute_lua_source_search' for x in tools),tools
 before=project_tools.status()
 async with websockets.connect(f'ws://127.0.0.1:{port}/ws',origin='http://127.0.0.1:7353') as ws:
  await asyncio.wait_for(ws.recv(),6)
  found,events=await ask(ws,'/code FR_NowNavRepeatsTitle')
  assert 'ForeverRoute_UIv2.lua:1058' in found,found
  assert 'pouze čtení' in found,found
  assert any('foreverroute_lua_source_search' in x.get('text','') for x in events),events
  print('REAL_SOURCE_SEARCH_PASS',flush=True)
  missing,_=await ask(ws,'/code UnknownLuaIdentifierZZ3344')
  assert 'nenašel' in missing,missing
  print('NO_HALLUCINATED_SOURCE_PASS',flush=True)
 after=project_tools.status()
 assert before['commit']==after['commit'] and before['changed_count']==after['changed_count']
 print('UNCHANGED_PROJECT_PASS',flush=True)
if __name__=='__main__':asyncio.run(main(int(sys.argv[1]) if len(sys.argv)>1 else 7361))