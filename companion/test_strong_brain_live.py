"""Real V2 original dashboard WebSocket on isolated staging port."""
import asyncio,json,sys,websockets
PORT=7362

async def ask(ws,text):
    await ws.send(json.dumps({'type':'chat','text':text},ensure_ascii=False))
    received=[]
    for n in range(35):
        event=json.loads(await asyncio.wait_for(ws.recv(),110))
        received.append(event)
        if event.get('type')=='done':break
    assert received[-1]['type']=='done'
    answers=[e['text'] for e in received if e.get('type')=='assistant']
    assert len(answers)==1
    return answers[0],received

async def main():
    async with websockets.connect(f'ws://127.0.0.1:{PORT}/ws',origin='http://127.0.0.1:7353') as ws:
        await ws.recv()
        safe,events=await ask(ws,'Silnější AI: password=super_secret')
        assert 'nelze bezpečně odeslat' in safe,safe
        print('SENSITIVE_CLOUD_REQUEST_BLOCKED',flush=True)
        ordinary,_=await ask(ws,'Kolik je dva plus dva?')
        assert 'čtyři' in ordinary,ordinary
        print('NORMAL_LOCAL_CHAT_UNCHANGED',flush=True)
        cloud,events=await ask(ws,'Silnější AI: Vysvětli stručně, jak v Lua 5.1 funguje gsub a proč se testuje oprava.')
        assert ('externí AI' in cloud or 'lokální AI' in cloud or 'neodpověděly' in cloud),cloud
        print('FREE_CLOUD_ATTEMPT_WITH_HONEST_FALLBACK',flush=True)
        print(json.dumps({'cloud_excerpt':cloud[:200],
           'events':[e.get('type') for e in events]},ensure_ascii=True),flush=True)
if __name__=='__main__':
    PORT=int(sys.argv[1]) if len(sys.argv)>1 else 7362
    asyncio.run(main())
