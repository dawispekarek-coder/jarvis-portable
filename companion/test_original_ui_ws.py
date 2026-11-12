"""Test original Jarvis UI WebSocket contract against isolated V2."""
import asyncio,json,websockets

async def question(ws,message):
    await ws.send(json.dumps({'type':'chat','text':message},ensure_ascii=False))
    events=[]
    for i in range(40):
        event=json.loads(await asyncio.wait_for(ws.recv(),10))
        events.append(event)
        if event.get('type')=='done':break
    assert events[-1].get('type')=='done',events
    answers=[e.get('text','') for e in events if e.get('type')=='assistant']
    assert answers,'Missing assistant reply'
    return answers[-1], [e.get('type') for e in events]

async def main():
    async with websockets.connect('ws://127.0.0.1:7353/ws') as ws:
        banner=json.loads(await asyncio.wait_for(ws.recv(),6))
        assert banner['type']=='info' and '2.0' in banner['text']
        await ws.send(json.dumps({'type':'ping'}))
        assert json.loads(await asyncio.wait_for(ws.recv(),6))['type']=='pong'
        cases=[('Kolik je dva plus dva?','čtyři'),('Ověř Lua testy ForeverRoute','3 failed'),('Najdi obrázky kachniček','zatím neumí'),('stop','žádný další úkol')]
        for prompt,expect in cases:
            answer,events=await question(ws,prompt)
            assert expect in answer,(prompt,answer)
            print('PASS',prompt,'EVENTS',','.join(events),'REPLY',answer[:90],flush=True)
    print('ORIGINAL_UI_WS_4_OF_4_PASS',flush=True)
if __name__=='__main__':
    asyncio.run(main())