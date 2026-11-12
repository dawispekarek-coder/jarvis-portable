import asyncio,json,sys,websockets
async def main(port):
 async with websockets.connect(f'ws://127.0.0.1:{port}/ws',origin='http://127.0.0.1:7353') as ws:
  await asyncio.wait_for(ws.recv(),6)
  await ws.send(json.dumps({'type':'chat','text':'Najdi LangGraph Python documentation'},ensure_ascii=False))
  answer='';types=[]
  for _ in range(40):
   event=json.loads(await asyncio.wait_for(ws.recv(),115))
   types.append(event.get('type'))
   if event.get('type')=='assistant': answer=event.get('text','')
   if event.get('type')=='done': break
  assert types[-1]=='done',types
  assert 'Použité zdroje:' in answer,answer
  assert 'Kontrola podkladů:' in answer,answer
  assert 'Doporučená další kontrola:' in answer,answer
  assert 'https://docs.langchain.com' in answer,answer
  print('EVIDENCE_LIVE_WS_PASS',len(answer),','.join(types),flush=True)
if __name__=='__main__':asyncio.run(main(int(sys.argv[1]) if len(sys.argv)>1 else 7379))