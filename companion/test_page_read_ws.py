"""Live WebSocket test of search-result-to-page-reader with source provenance."""
import asyncio,json,sys,websockets
async def ask(ws,text):
 await ws.send(json.dumps({"type":"chat","text":text},ensure_ascii=False))
 events=[]
 for _ in range(24):
  ev=json.loads(await asyncio.wait_for(ws.recv(),31))
  events.append(ev)
  if ev["type"]=="done":break
 answers=[e["text"] for e in events if e["type"]=="assistant"]
 assert len(answers)==1 and events[-1]["type"]=="done",events
 return answers[0]
async def main(port):
 async with websockets.connect(f"ws://127.0.0.1:{port}/ws",origin="http://127.0.0.1:7353") as ws:
  await asyncio.wait_for(ws.recv(),6)
  empty=await ask(ws,"/read 1")
  assert "Nejdřív proveď" in empty,empty
  print("NO_UNAUTHORIZED_URL_READ_PASS",flush=True)
  links=await ask(ws,"/web LangGraph Python documentation")
  assert "docs.langchain.com" in links,links
  print("WEB_DISCOVERY_PASS",flush=True)
  page=await ask(ws,"/read 1")
  assert "Načtený text z veřejné stránky" in page,page
  assert "Zdroj: https://docs.langchain.com/" in page,page
  assert "LangGraph" in page,page
  assert "neověřené tvrzení" in page,page
  print("PUBLIC_PAGE_CONTENT_WITH_SOURCE_PASS",len(page),flush=True)
  refs=await ask(ws,"/web ForeverRoute wow addon")
  assert "curseforge.com/wow/addons/foreverroute" in refs,refs
  blocked=await ask(ws,"/read 1")
  assert "nepodařilo bezpečně přečíst" in blocked,blocked
  print("ANTIBOT_FAIL_CLOSED_PASS",flush=True)
if __name__=="__main__":asyncio.run(main(int(sys.argv[1]) if len(sys.argv)>1 else 7369))