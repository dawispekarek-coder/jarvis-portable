"""Real original UI WS conversation reveals actual self-learning state."""
import asyncio,json,sys,websockets
PORT=7395
async def ask(ws,text):
    await ws.send(json.dumps({'type':'chat','text':text},ensure_ascii=False))
    answer=[]
    for _ in range(25):
        e=json.loads(await asyncio.wait_for(ws.recv(),30))
        if e.get('type')=='assistant':answer.append(e.get('text',''))
        if e.get('type')=='done':break
    assert len(answer)==1,answer
    return answer[0]
async def main():
    async with websockets.connect(f'ws://127.0.0.1:{PORT}/ws',origin='http://127.0.0.1:7353') as ws:
        await asyncio.wait_for(ws.recv(),5)
        text=await ask(ws,'Co ses naučil?')
        assert 'ověřených pokusů' in text and 'modelu' in text,text
        print('TRUE_SELF_LEARNING_CHAT_PASS',text[:220],flush=True)
        answer=await ask(ws,'Najdi v souborech slovo heslo')
        assert 'webových zdrojů' not in answer,answer
        print('LOCAL_SEARCH_NOT_EXPORTED_PASS',flush=True)
if __name__=='__main__':
    PORT=int(sys.argv[1]) if len(sys.argv)>1 else 7395
    asyncio.run(main())