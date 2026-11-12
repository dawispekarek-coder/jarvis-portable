"""Real WebSocket memory smoke test; removes its own test note."""
import asyncio,json,sys,uuid,websockets
from knowledge_store import NoteStore
from pathlib import Path

URL='ws://127.0.0.1:7355/ws'
STORE=NoteStore(Path(__file__).parent/'user_notes.sqlite')

async def ask(prompt):
    async with websockets.connect(URL,origin='http://127.0.0.1:7353') as ws:
        banner=json.loads(await asyncio.wait_for(ws.recv(),6))
        assert banner['type']=='info'
        await ws.send(json.dumps({'type':'chat','text':prompt},ensure_ascii=False))
        answer=None
        for _ in range(30):
            event=json.loads(await asyncio.wait_for(ws.recv(),10))
            if event.get('type')=='assistant':answer=event.get('text','')
            if event.get('type')=='done':
                assert answer is not None
                return answer
        raise AssertionError('missing done')

async def main():
    unique='TestPameti'+uuid.uuid4().hex[:10]
    try:
        a=await ask('Zapamatuj si: '+unique+' ma stav ZELENA')
        assert 'Uložil' in a,a
        b=await ask('Co si pamatuješ o '+unique+'?')
        assert unique in b and 'ZELENA' in b and 'neověřené' in b,b
        print('LIVE_NOTES_PERSISTED_BETWEEN_WS_CONNECTIONS_PASS')
        c=await ask('Znalosti: Jaké levely pokrývá beta ForeverRoute?')
        assert 'ForeverRoute/' in c and '1-60' in c,c
        print('DOCUMENT_KNOWLEDGE_STILL_WORKS_PASS')
        d=await ask('Kolik je dva plus dva?')
        assert 'čtyři' in d,d
        print('ORDINARY_ARITHMETIC_STILL_WORKS_PASS')
        empty=await ask('Co si pamatuješ o NeexistujiciPoznamce'+uuid.uuid4().hex+'?')
        assert 'žádnou poznámku' in empty,empty
        print('NO_FAKE_NOTES_PASS')
    finally:
        for n in STORE.search(unique):
            if unique in n['content']:
                STORE.forget(n['id'])
        assert not STORE.search(unique),'test note cleanup failed'
        print('TEST_NOTE_CLEANED')
if __name__=='__main__':
    port=int(sys.argv[1]) if len(sys.argv)>1 else 7355
    URL=f'ws://127.0.0.1:{port}/ws'
    asyncio.run(main())