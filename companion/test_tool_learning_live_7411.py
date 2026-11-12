import asyncio,json,websockets,urllib.request
async def main():
 async with websockets.connect('ws://127.0.0.1:7411/ws',origin='http://127.0.0.1:7411') as ws:
  init=json.loads(await asyncio.wait_for(ws.recv(),6));assert init['type']=='info'
  for q,needle in [('Stav učení nástrojů','Stav výuky'),('Nauč se pracovat se vším, co máš k dispozici','Prošel jsem 19'),('Co všechno umíš?','Moje skutečné možnosti')]:
   await ws.send(json.dumps({'type':'chat','text':q},ensure_ascii=False))
   types=[];replies=[]
   for _ in range(40):
    event=json.loads(await asyncio.wait_for(ws.recv(),40));types.append(event['type'])
    if event['type']=='assistant':replies.append(event.get('text',''))
    if event['type']=='done':break
   assert types[-1]=='done' and len(replies)==1 and needle in replies[0],(q,types,replies)
   print('LIVE_WS_PASS',q,'chars',len(replies[0]),'types',','.join(types),flush=True)
 with urllib.request.urlopen('http://127.0.0.1:7411/api/tool-learning/status',timeout=5) as r: status=json.load(r)
 assert status['status']=='COMPLETED' and status['checked']==19,status
 print('PERSISTENCE_PASS',status['status'],'skills',len(status['skills']))
if __name__=='__main__':asyncio.run(main())

