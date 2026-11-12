import asyncio,json,urllib.request,sys,websockets
async def ask(ws,prompt):
 await ws.send(json.dumps({'type':'chat','text':prompt},ensure_ascii=False))
 events=[]
 for _ in range(20):
  e=json.loads(await asyncio.wait_for(ws.recv(),23))
  events.append(e)
  if e['type']=='done':break
 answers=[e.get('text','') for e in events if e['type']=='assistant']
 assert len(answers)==1 and events[-1]['type']=='done',events
 return answers[0],events
async def run(port):
 with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/tools',timeout=6) as r:
  tools=json.load(r)
 assert any(x['name']=='web_search_public' for x in tools),tools
 async with websockets.connect(f'ws://127.0.0.1:{port}/ws',origin='http://127.0.0.1:7353') as ws:
  await asyncio.wait_for(ws.recv(),5)
  a,e=await ask(ws,'/web LangGraph Python documentation')
  assert 'DuckDuckGo Lite' in a and 'https://docs.langchain.com/' in a,a
  assert 'neověřený obsah' in a or 'neověřený obsah' in str(e),a
  print('LIVE_SEARCH_LINKS_PASS',len(a),flush=True)
  b,e=await ask(ws,'/web ForeverRoute wow addon')
  assert 'https://www.curseforge.com/wow/addons/foreverroute' in b,b
  print('LIVE_PROJECT_RESULT_PASS',len(b),flush=True)
if __name__=='__main__':asyncio.run(run(int(sys.argv[1]) if len(sys.argv)>1 else 7362))