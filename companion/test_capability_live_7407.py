import asyncio,json,websockets
async def main():
 async with websockets.connect('ws://127.0.0.1:7407/ws',origin='http://127.0.0.1:7407') as ws:
  init=json.loads(await ws.recv());assert init['type']=='info',init
  for query,needle in [('Máš připojené TTS?','TTS API v JARVIS 2.0 je propojené'),('Co všechno umíš?','Moje skutečné možnosti'),('Dokážeš programovat ForeverRoute?','Zápis a autonomní nasazení není povolené'),('Máš internet?','momentální konektivita vyžaduje test')]:
   await ws.send(json.dumps({'type':'chat','text':query},ensure_ascii=False))
   replies=[]
   for _ in range(12):
    event=json.loads(await asyncio.wait_for(ws.recv(),10))
    if event['type']=='assistant':replies.append(event['text'])
    if event['type']=='done':break
   assert len(replies)==1 and needle in replies[0],(query,replies)
   print('LIVE_WS_PASS',query,replies[0][:130].replace('\n',' '))
asyncio.run(main())
