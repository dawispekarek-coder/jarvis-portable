import asyncio,json,re,urllib.request,websockets
from goal_workflow import extract_goal,latest,get
assert extract_goal('Jak se naučit česky?') is None
assert extract_goal('Najdi obrázky koček') is None
assert extract_goal('Zkontroluj Git ForeverRoute') is None
async def ask(ws,phrase):
    await ws.send(json.dumps({'type':'chat','text':phrase},ensure_ascii=False))
    events=[]
    for _ in range(18):
        msg=json.loads(await asyncio.wait_for(ws.recv(),30))
        events.append(msg)
        if msg.get('type')=='done':break
    assert events[-1]['type']=='done',events
    info=[v.get('text','') for v in events if v['type']=='info']
    m=next((re.search(r'Zalozen ukol ([0-9a-f]{8})',s) for s in info
            if 'Zalozen ukol' in s),None)
    assert m,events
    answers=[v for v in events if v['type']=='assistant']
    assert len(answers)==1,events
    task=next(x for x in latest(12) if x['id'].startswith(m.group(1)))
    assert task['status'] in ('CHECKPOINT','BLOCKED_CAPABILITY','WAITING_APPROVAL','FAILED'),task
    print('GOAL',phrase,'STATUS',task['status'],'CATEGORY',task['category'],
          'EVENTS',[x['type'] for x in events],flush=True)
    return task,answers[0]
async def main():
    async with websockets.connect('ws://127.0.0.1:7414/ws',
                  origin='http://127.0.0.1:7353') as ws:
        await asyncio.wait_for(ws.recv(),5)
        a,_=await ask(ws,'Nauč se pořádně česky')
        assert a['category']=='czech' and a['status']=='CHECKPOINT',a
        assert a['evidence']['total']>=200,a
        b,_=await ask(ws,'Oprav si hlas')
        assert b['category']=='voice' and b['status']=='CHECKPOINT'
        assert b['evidence']['tts_http_bridge'] is True
        c,_=await ask(ws,'Zjisti co máš k dispozici a nauč se to používat')
        assert c['category']=='capabilities' and c['status']=='CHECKPOINT'
        d,_=await ask(ws,'Nainstaluj software')
        assert d['status']=='WAITING_APPROVAL',d
    with urllib.request.urlopen('http://127.0.0.1:7414/api/goals',timeout=6) as r:
        data=json.load(r)
    assert len(data['tasks'])>=4
    print('GOAL_E2E_PASS',len(data['tasks']),flush=True)
if __name__=='__main__':asyncio.run(main())

