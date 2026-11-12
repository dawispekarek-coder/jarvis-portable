import asyncio,json,websockets
from in_app_media import image_query,link_cards,web_url
assert image_query('najdi obrázky koček')=='kocek'
assert image_query('Otevři prohlížeč a najdi obrázky koček')=='kocek'
assert image_query('najdi informace o kočkách') is None
assert image_query('Hledej na webu bankovní účet') is None
assert not web_url('javascript:alert(1)')
assert len(link_cards({'pages':[{'url':'https://example.org/','title':'X'}]}))==1

async def run():
    async with websockets.connect('ws://127.0.0.1:7398/ws',
                 origin='http://127.0.0.1:7353') as ws:
        await asyncio.wait_for(ws.recv(),5)
        await ws.send(json.dumps({'type':'chat','text':'najdi obrázky koček'}))
        events=[]
        for _ in range(16):
            event=json.loads(await asyncio.wait_for(ws.recv(),45))
            events.append(event)
            if event.get('type')=='done':break
        cards=[e for e in events if e.get('type')=='media' and e.get('kind')=='images']
        assert cards,events
        assert len(cards[0]['items'])>=1,cards
        assert all(web_url(i['url']) and web_url(i['thumbnail']) for i in cards[0]['items'])
        assert events[-1]['type']=='done',events
        assert any(e.get('type')=='assistant' for e in events)
        print('MEDIA_WS_PASS',len(cards[0]['items']),[e.get('type') for e in events])
asyncio.run(run())
