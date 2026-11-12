import asyncio,json,sys,websockets
PORT=7354
URL=f'ws://127.0.0.1:{PORT}/ws'
async def turn(ws,prompt):
    await ws.send(json.dumps({'type':'chat','text':prompt},ensure_ascii=False))
    kinds=[];answers=[]
    for i in range(45):
        e=json.loads(await asyncio.wait_for(ws.recv(),12))
        kinds.append(e.get('type'))
        if e.get('type')=='assistant':answers.append(e.get('text',''))
        if e.get('type')=='done':break
    assert kinds[-1]=='done' and answers,(prompt,kinds)
    return answers[-1]
async def main():
    async with websockets.connect(URL,origin='http://127.0.0.1:7353') as ws:
        await asyncio.wait_for(ws.recv(),6)
        a=await turn(ws,'Znalosti: Jaké levely pokrývá beta ForeverRoute?')
        assert '1-60' in a and 'ForeverRoute/README.md:1' in a,a
        print('CITED_DOC_PASS',len(a),flush=True)
        b=await turn(ws,'Znalosti: zxcvnothere39819')
        assert 'nenašel' in b and 'vymýšlet' in b,b
        print('NO_FAKE_KNOWLEDGE_PASS',flush=True)
        c=await turn(ws,'Kolik je dva plus dva?')
        assert 'čtyři' in c,c
        print('EXISTING_MATH_UNCHANGED_PASS',flush=True)
    print('ALL_3_LIVE_KNOWLEDGE_WS_TESTS_PASS',flush=True)
if __name__=='__main__':
    PORT=int(sys.argv[1]) if len(sys.argv)>1 else 7354
    URL=f'ws://127.0.0.1:{PORT}/ws'
    asyncio.run(main())