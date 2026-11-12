import asyncio,json,websockets
URL='ws://127.0.0.1:7353/ws'
async def run():
    async with websockets.connect(URL,origin='http://127.0.0.1:7353') as ws:
        banner=json.loads(await ws.recv())
        assert banner['type']=='info'
        print('SAME_ORIGIN_ALLOWED',flush=True)
    try:
        async with websockets.connect(URL,origin='https://evil.example'):
            raise AssertionError('CROSS_ORIGIN_ACCEPTED')
    except websockets.exceptions.InvalidStatus as e:
        assert e.response.status_code==403
        print('FOREIGN_ORIGIN_DENIED_403',flush=True)
asyncio.run(run())