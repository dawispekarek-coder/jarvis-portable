"""Full original-ui WebSocket: find => browser+search+page+summary."""
import asyncio,json,sys,websockets
PORT=7377
async def send(ws,text):
    await ws.send(json.dumps({'type':'chat','text':text},ensure_ascii=False))
    out=[]
    for i in range(45):
        event=json.loads(await asyncio.wait_for(ws.recv(),130))
        out.append(event)
        if event.get('type')=='done':break
    assert out[-1].get('type')=='done',out
    answers=[x['text'] for x in out if x.get('type')=='assistant']
    assert len(answers)==1
    return answers[0],out
async def main():
    async with websockets.connect(f'ws://127.0.0.1:{PORT}/ws',origin='http://127.0.0.1:7353') as ws:
        await ws.recv()
        ans,events=await send(ws,'Najdi Lua 5.1 official manual gsub')
        assert 'www.lua.org' in ans and 'Použité zdroje:' in ans,ans
        assert 'Shrnutí skutečně načtených' in ans,ans
        assert any(x.get('type')=='info' and 'Web:' in x.get('text','') for x in events),events
        print('PASS_REAL_SEARCH_READ_SUMMARY',len(ans),flush=True)
        local,events=await send(ws,'Najdi v souborech heslo')
        assert not any(x.get('type')=='info' and 'Web:' in x.get('text','') for x in events),events
        print('PASS_LOCAL_CONTENT_NOT_WEB_ROUTED',flush=True)
        ordinary,events=await send(ws,'Kolik je dva plus dva?')
        assert 'čtyři' in ordinary,ordinary
        print('PASS_EXISTING_LOCAL_CHAT',flush=True)
if __name__=='__main__':
    PORT=int(sys.argv[1]) if len(sys.argv)>1 else 7377
    asyncio.run(main())