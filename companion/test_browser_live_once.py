import asyncio,json,websockets
async def main():
 async with websockets.connect("ws://127.0.0.1:7421/ws",origin="http://127.0.0.1:7421") as ws:
  await asyncio.wait_for(ws.recv(),8)
  await ws.send(json.dumps({"type":"chat","text":"Otevři prohlížeč"},ensure_ascii=False))
  replies=[]
  for _ in range(12):
   item=json.loads(await asyncio.wait_for(ws.recv(),12))
   if item.get("type")=="assistant":replies.append(item.get("text",""))
   if item.get("type")=="done":break
  assert len(replies)==1,replies
  assert "https://www.google.com/" in replies[0],replies
  assert "Nacteni stranky nebylo overeno" in replies[0],replies
  print("LIVE_WS_BROWSER_COMMAND_PASS",replies[0])
if __name__=='__main__':asyncio.run(main())

