from pathlib import Path
import shutil,ast
p=Path(r'H:\RealJarvis\V2Sandbox\BrainCore\ui_compat.py')
raw=p.read_bytes();s=raw.decode('utf-8')
nl='\n' if s.count('\n')>2*s.count('\r\n') else '\r\n'
def add(before,after):
    global s
    assert s.count(before)==1,before
    s=s.replace(before,after,1)
def block(src):return src.replace('\n',nl)
add('from adaptive_research import research as full_web_research',
    'from adaptive_research import research as full_web_research'+nl+
    'from in_app_media import image_query,image_results,link_cards')
add('                opened=await asyncio.to_thread(open_search_window,query)'+nl,'')
add("                reply=data['reply']",block("""                cards=link_cards(data)
                if cards:
                    await notify(ws,'media',kind='search',items=cards,
                                 query=query,tool='web_search')
                reply=data['reply']"""))
start=s.index("                msg='Edge:")
end=s.index(nl,start)
s=s[:start]+"                msg='Zdroje jsou v galerii Jarvise'"+s[end:]
add('    async def run_public_search(query:str):',block("""    async def run_image_search(query:str):
        if PRIVATE_WEB_QUERY.search(query):
            reply='Citlive udaje neposilam na web.'
        else:
            await notify(ws,'thinking',text='Hledam obrazky...')
            try:
                items=await asyncio.wait_for(asyncio.to_thread(image_results,query),timeout=39)
            except Exception:
                items=[]
            if items:
                await notify(ws,'media',kind='images',items=items,
                             summary=f'{len(items)} obrazku',query=query,tool='image_search')
                reply=f'Zobrazil jsem {len(items)} obrazku v galerii Jarvise.'
            else:
                reply='Vyhledavac neposkytl obrazky. Nic jsem nevymyslel.'
        await notify(ws,'assistant',text=reply,speak=False)
        await notify(ws,'done')

    async def run_public_search(query:str):"""))
add('            ordinary_web_query=extract_web_intent(text)',block("""            image_request=image_query(text)
            if image_request is not None:
                active=asyncio.create_task(run_image_search(image_request))
                continue
            ordinary_web_query=extract_web_intent(text)"""))
ast.parse(s)
assert p.read_bytes()==raw,'concurrent edit'
backup=p.with_name('ui_compat.py.before_inline_media_20261027.bak')
assert not backup.exists()
shutil.copy2(p,backup)
p.write_bytes(s.encode('utf-8'))
print('PATCH_APPLIED',len(raw),len(s.encode('utf-8')))

