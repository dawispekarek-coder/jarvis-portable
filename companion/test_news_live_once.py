import asyncio,json,websockets
async def main():
 async with websockets.connect("ws://127.0.0.1:7423/ws",origin="http://127.0.0.1:7353") as ws:
  await asyncio.wait_for(ws.recv(),8)
  await ws.send(json.dumps({"type":"chat","text":"Shrň mi dnešní zprávy"},ensure_ascii=False))
  messages=[]
  for i in range(30):
   d=json.loads(await asyncio.wait_for(ws.recv(),120))
   messages.append(d)
   if d.get("type")=="done":break
  replies=[d.get("text","") for d in messages if d.get("type")=="assistant"]
  assert replies,replies
  print("RESULT",json.dumps({"reply":replies[-1][:1200],"events":[d.get("type") for d in messages]},ensure_ascii=False))
  assert "Lokální AI (v této odpovědi" not in replies[-1]
  assert "Lokální AI (bez internetu" not in replies[-1]
asyncio.run(main())
