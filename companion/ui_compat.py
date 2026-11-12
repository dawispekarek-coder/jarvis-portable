"""Original RealJarvis dashboard + isolated V2 WebSocket protocol adapter.
Original UI assets are copied byte-for-byte. NO production tool access.
"""
import asyncio,json,re,platform,urllib.request,urllib.error,threading
import psutil
from pathlib import Path
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,Request
from fastapi.responses import FileResponse,JSONResponse,Response
from fastapi.staticfiles import StaticFiles
from task_engine import Engine,ROOT
from goal_workflow import (create as goal_create,run as goal_run,
     extract_goal as goal_extract,format_result as goal_format,
     latest as goal_latest,get as goal_get,cancel as goal_cancel,
     recover_stale as goal_recover)
from knowledge_store import NoteStore,handle_command
from local_chat import extract_request,answer_local,LocalModelUnavailable
from grounded_chat import extract_request as extract_grounded_request,answer_grounded
from general_brain import generate as answer_general,unconnected_action
from strong_brain_router import extract as extract_strong, answer as answer_strong
from project_tools import extract as is_repo_status,status as get_repo_status,format_status as format_repo_status
from project_tools import extract_code_search,search_lua,format_code_search
from foreverroute_study import intent as project_study_intent,study as read_project_study,format_study
from inspect_agent import extract_goal as is_inspection_goal,inspect as inspect_project,format_report as format_inspection
from public_search import extract_request as extract_web_request,search as live_web_search,format_results as format_web_results,SearchUnavailable
from page_reader import extract_read_command,read_result,format_read,PageUnavailable
from behavior_router import extract_web_intent
from adaptive_research import research as full_web_research
from in_app_media import image_query,image_results,link_cards
from experience_learning import summary as experience_summary,explain as learning_explain,is_learning_question
from search_browser import open_search_window,SENSITIVE as PRIVATE_WEB_QUERY
from internet_access import intent as internet_intent,check_or_connect as internet_connect,format_result as internet_result
from browser_commands import intent as browser_intent, execute as browser_execute
import knowledge
from capability_inventory import inventory as capability_inventory, answer as capability_answer
from tool_learning import training_intent, train_all, current as tool_learning_status, format_report as training_report, format_status as training_status_text

UI=ROOT/'OriginalJarvisUI'
ENG=Engine(ROOT/'BrainCore'/'tasks.sqlite')
NOTES=NoteStore(ROOT/'BrainCore'/'user_notes.sqlite')
app=FastAPI(title='RealJarvis V2 Original UI Adapter',docs_url=None,redoc_url=None)
app.mount('/assets',StaticFiles(directory=str(UI/'assets')),name='assets')

@app.get('/')
def ui_home():
    return FileResponse(UI/'index.html',headers={'Cache-Control':'no-store'})

@app.get('/favicon.svg')
def favicon():
    return FileResponse(UI/'favicon.svg')

@app.get('/health')
def health():
    return {'status':'online','service':'RealJarvis V2 pilot','production_attached':False,
            'coding_agent_enabled':False,'ui':'original','tool_scope':['arithmetic','lua_audit','knowledge_search','local_conversation','foreverroute_git_status_readonly','foreverroute_lua_source_search_readonly','web_search_public_readonly','web_page_reader_readonly','foreverroute_inspection_graph_readonly']}

@app.get('/api/learning/status')
def learning_status():return experience_summary()
@app.get('/api/tool-learning/status')
def tool_learning_api_status():return tool_learning_status()
@app.get('/api/behavior/status')
def behavior_status():
    guide=ROOT/'JARVIS_PROVOZNI_MANUAL_V4.txt'
    return {'active':True,'manual_installed':guide.is_file(),
            'manual_path':str(guide),'default_model_retrained':False,'experience_learning_active':True,
            'natural_find_routes_to':'browser+public_search+page_read+local_summary',
            'local_find_is_private':True,'write_actions_authorized':False}
@app.get('/api/health')
def api_health():
    return {'status':'online','name':'REALJARVIS V2 — TEST',
            'model':{'provider':'ollama-local','model':'qwen3.5:4b-q4_K_M','configured':True,'default_chat':True},
            'tools':len(tools()),'plugins':[],'agents':[],'production_attached':False,
            'permission_mode':'isolated','image_model':'disabled',
            'voice':{'wake_word':''}}

@app.get('/api/agents')
def agents():return []
@app.get('/api/tools')
def tools():return [{"name":"foreverroute_git_status","description":"Přečti větev, poslední commit a změněné soubory ForeverRoute.","permission":"read-only"},{"name":"foreverroute_lua_source_search","description":"Vyhledej konkrétní Lua symbol ve zdrojovém kódu ForeverRoute.","permission":"read-only"},{"name":"web_search_public","description":"Hledej veřejné odkazy přes DuckDuckGo Lite; bez čtení obsahu stránek.","permission":"read-only"},{"name":"foreverroute_inspection_graph","description":"Zkontroluj Git, vyhledej Lua funkci a ověř izolovaný test bez úprav addonu.","permission":"read-only"},{"name":"web_page_reader","description":"Přečti omezený text očíslovaného výsledku veřejného vyhledávání.","permission":"read-only"},{"name":"internet_connect_verified","description":"Na pokyn ověř internet a případně bezpečně obnov jedinou uloženou Wi-Fi.","permission":"bounded network action"}]
@app.get('/api/plugins')
def plugins():return []
@app.get('/api/memory/search')
async def memory_search(q:str=''):
    return {'results':await asyncio.to_thread(knowledge.search,q)}

@app.get('/api/knowledge/status')
def knowledge_status():return knowledge.status()

@app.get('/api/knowledge/search')
async def knowledge_search(q:str=''):
    return {'query':q[:250],'results':await asyncio.to_thread(knowledge.search,q)}
@app.get('/api/capabilities')
def capabilities():return capability_inventory()
VOICE_BACKEND='http://127.0.0.1:7341'
def _voice_backend(path,body=None):
    headers={'Accept':'application/json'}
    if body is not None:headers['Content-Type']='application/json'
    req=urllib.request.Request(VOICE_BACKEND+path,data=body,headers=headers,method='POST' if body is not None else 'GET')
    with urllib.request.urlopen(req,timeout=60 if body is not None else 3) as resp:
        return resp.read(),resp.headers.get('Content-Type','application/octet-stream')
@app.get('/api/tts/status')
async def voice_status():
    try:
        raw,_=await asyncio.to_thread(_voice_backend,'/api/tts/status')
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return {'available':False,'provider':'supertonic3-unavailable','voice':'M3-Digital13','label':'Supertonic 3 - M3 Digital 13','lang':'cs-CZ'}
@app.post('/api/tts')
async def voice_tts(req:Request):
    body=await req.body()
    try:
        raw,ctype=await asyncio.to_thread(_voice_backend,'/api/tts',body)
        return Response(content=raw,media_type=ctype.split(';',1)[0])
    except urllib.error.HTTPError as exc:
        return Response(content=exc.read(),status_code=exc.code,media_type=exc.headers.get_content_type())
    except Exception as exc:
        return JSONResponse({'error':'tts_unavailable','detail':str(exc)[:160]},status_code=503)
@app.get('/api/chatgpt/status')
def chatgpt_status():return {'connected':False,'provider':'not-in-v2'}
@app.get('/api/image-models')
def image_models():return {'selected':'','models':[]}
@app.get('/api/stats')
def stats():
    memory=psutil.virtual_memory()
    try:volume=psutil.disk_usage(str(ROOT.anchor))
    except OSError:volume=psutil.disk_usage('C:\\')
    network=psutil.net_io_counters()
    return {
        'cpu':psutil.cpu_percent(interval=None),
        'cpu_count':psutil.cpu_count(logical=True) or 1,
        'ram':{'percent':memory.percent,'used_gb':round(memory.used/1e9,2),'total_gb':round(memory.total/1e9,2)},
        'disk':{'percent':volume.percent,'used_gb':round(volume.used/1e9,2),'total_gb':round(volume.total/1e9,2)},
        'net':{'sent_mb':round(network.bytes_sent/1e6,2),'recv_mb':round(network.bytes_recv/1e6,2)},
        'os':{'system':platform.system(),'release':platform.release(),'node':platform.node()},
        'gpu':{'available':False}}
@app.get('/api/processes')
def processes(limit:int=12):return []

@app.post('/tasks')
async def create_task(req:Request):
    try:payload=await req.json()
    except (ValueError,TypeError):return JSONResponse({'error':'invalid_json'},400)
    if not isinstance(payload,dict):return JSONResponse({'error':'invalid_json'},400)
    kind=payload.get('kind');goal=payload.get('goal')
    if kind not in ('arithmetic','lua_audit','coding_proposal') or not isinstance(goal,str) or not 1<=len(goal)<=1200:
        return JSONResponse({'error':'invalid_task'},400)
    s=ENG.create(kind,goal)
    if payload.get('run') is True:s=await asyncio.to_thread(ENG.run,s['id'])
    return JSONResponse(s,status_code=201)

@app.get('/tasks/{id}')
def task_status(id:str):
    try:return ENG.store.get(id)
    except KeyError:return JSONResponse({'error':'not_found'},404)

@app.post('/tasks/{id}/cancel')
def cancel_task(id:str):
    try:return ENG.cancel(id)
    except KeyError:return JSONResponse({'error':'not_found'},404)

@app.get('/api/logs/stream')
async def logs_unavailable():
    return JSONResponse({'error':'V2 logs not integrated yet'},status_code=501)

@app.get('/api/goals')
def goal_tasks(limit:int=10):
    return {'tasks':goal_latest(limit)}

@app.get('/api/goals/{goal_id}')
def goal_status(goal_id:str):
    try:return goal_get(goal_id)
    except KeyError:return JSONResponse({'error':'goal_not_found'},404)

@app.post('/api/goals')
async def start_goal(req:Request):
    try:
        body=await req.json()
        goal=body.get('goal','') if isinstance(body,dict) else ''
        task=await asyncio.to_thread(goal_create,goal)
        if isinstance(body,dict) and body.get('run') is True:
            task=await asyncio.to_thread(goal_run,task['id'])
        return JSONResponse(task,status_code=201)
    except (ValueError,TypeError):
        return JSONResponse({'error':'not_an_action_goal'},400)

@app.post('/api/goals/{goal_id}/cancel')
def cancel_goal(goal_id:str):
    try:return goal_cancel(goal_id)
    except KeyError:return JSONResponse({'error':'goal_not_found'},404)

@app.api_route('/api/{path:path}',methods=['GET','POST','PUT','PATCH','DELETE'])
async def unavailable_api(path:str):
    return JSONResponse({'error':'unsupported_v2','message':'Funkce zatím není připojená k RealJarvis 2.0.'},status_code=501)


def knowledge_query(text:str)->str|None:
    value=text.strip()
    lower=value.casefold()
    for prefix in ('znalosti:','znalost:','/knowledge ','v dokumentaci ','najdi v dokumentaci ','ve znalostech '):
        if lower.startswith(prefix):
            return value[len(prefix):].strip() or 'ForeverRoute'
    return None
def kind_from_text(text:str)->str|None:
    normalized=text.casefold().strip()
    if re.search(r'\b(?:2\s*\+\s*2|dva\s+plus\s+dva)\b',normalized):return 'arithmetic'
    if 'lua' in normalized or 'foreverroute' in normalized:
        if any(k in normalized for k in ('oprav','edit','programuj','změň','upravit','naprogramuj','fix')):
            return 'coding_proposal'
        return 'lua_audit' if any(k in normalized for k in ('test','kontrol','audit','ověř','over','simul')) else None
    return None

async def notify(ws:WebSocket,type:str,**kwargs):
    await ws.send_json({'type':type,**kwargs})

@app.websocket('/ws')
async def original_ws(ws:WebSocket):
    origin=ws.headers.get('origin')
    if origin and origin not in ('http://127.0.0.1:7353','http://localhost:7353','http://127.0.0.1:7398','http://localhost:7398','http://127.0.0.1:7399','http://localhost:7399','http://127.0.0.1:7407','http://localhost:7407','http://127.0.0.1:7411','http://localhost:7411','http://127.0.0.1:7412','http://localhost:7412'):
        await ws.close(code=1008)
        return
    await ws.accept()
    await notify(ws,'info',text='REALJARVIS 2.0 — TEST • původní vzhled • nové jádro, zatím omezené funkce')
    active:asyncio.Task|None=None
    training_stop:threading.Event|None=None
    taskid:str|None=None
    goal_task_id:str|None=None
    chat_history:list[dict]=[]
    recent_web_hits:list[dict]=[]

    async def run_action_goal(goal:str):
        nonlocal goal_task_id
        try:
            item=await asyncio.to_thread(goal_create,goal)
            goal_task_id=item['id']
            await notify(ws,'info',text='Zalozen ukol '+item['id'][:8]+': '+goal[:140])
            await notify(ws,'thinking',text='Provadim prvni bezpecny krok a ukladam dukazy...')
            result=await asyncio.to_thread(goal_run,item['id'])
            output=goal_format(result)
            await notify(ws,'info',text='Ukol '+item['id'][:8]+' / '+result['status'])
            await notify(ws,'assistant',text=output,speak=True,
                         speech_text=('Ukol '+item['id'][:8]+'; '+result['status']
                                      +'. Prvni krok je zapsany, dalsi je v prehledu.')[:190])
            await notify(ws,'done')
        except asyncio.CancelledError:
            if goal_task_id:
                await asyncio.to_thread(goal_cancel,goal_task_id)
            raise
        except Exception:
            await notify(ws,'assistant',text='Ukol se nepodarilo spolehlive zalozit nebo overit. Netvrdim, ze jsem ho provedl.',speak=False)
            await notify(ws,'done')

    async def run_chat(text:str,kind:str):
        nonlocal taskid
        try:
            await notify(ws,'thinking',text='Zpracovávám v izolovaném jádru...')
            task=ENG.create(kind,text)
            taskid=task['id']
            done=await asyncio.to_thread(ENG.run,taskid)
            status=done['status']
            if status=='VERIFIED':reply=done.get('answer') or 'Ověřeno.'
            elif status=='WAITING_APPROVAL':
                reply='Programátorský agent ještě není připojený. Tento požadavek jsem neprovedl.'
            elif status=='CANCELLED':reply='Úkol byl zrušen.'
            else:
                reply=done.get('answer') or 'Úkol se nepodařilo ověřit.'
                if kind=='lua_audit':reply+='\nZměny se neprovedly; ověřovací test neprošel.'
            await notify(ws,'info',text='V2 úkol: '+status)
            await notify(ws,'assistant',text=reply,speak=False)
            await notify(ws,'done')
        except asyncio.CancelledError:
            if taskid:ENG.cancel(taskid)
            raise
        except Exception:
            await notify(ws,'error',text='Úkol selhal v testovacím jádru; produkční systém zůstal beze změny.')
            await notify(ws,'done')
    async def run_internet_command(action:str):
        try:
            await notify(ws,'thinking',text='Kontroluji skutečné internetové připojení a dostupnost webových nástrojů...')
            result=await asyncio.wait_for(asyncio.to_thread(internet_connect,action),timeout=37)
            reply=internet_result(result)
            await notify(ws,'info',text='V2 internet: '+('ONLINE' if result['connected'] else 'NEOVĚŘENO')+
                '; vyhledávání: '+('DOSTUPNÉ' if result['web_search_ready'] else 'NEDOSTUPNÉ'))
        except (OSError,ValueError,RuntimeError,asyncio.TimeoutError):
            reply='Kontrolu internetu jsem nedokázal dokončit. Nebudu tvrdit, že připojení funguje.'
        await notify(ws,'assistant',text=reply,speak=False)
        await notify(ws,'done')

    async def run_page_read(index:int):
        if not 1<=index<=len(recent_web_hits):
            await notify(ws,'assistant',text='Nejdřív proveď /web hledaný výraz. Potom zadej /read 1 až /read 6 podle nalezených výsledků.',speak=False)
            await notify(ws,'done')
            return
        try:
            await notify(ws,'thinking',text='Načítám veřejnou HTTPS stránku, bez spouštění jejího obsahu...')
            page=await asyncio.wait_for(asyncio.to_thread(read_result,recent_web_hits[index-1]),timeout=19)
            reply=format_read(page)
            await notify(ws,'info',text='V2 nástroj: veřejná HTTPS stránka přečtena; zdroj je neověřený text autora')
        except (PageUnavailable,OSError,ValueError,asyncio.TimeoutError):
            reply='Obsah této stránky se nepodařilo bezpečně přečíst (může být blokovaný nebo nedostupný). Odkaz nalezený ve vyhledávání není ověřený obsah stránky.'
        await notify(ws,'assistant',text=reply,speak=False)
        await notify(ws,'done')

    async def run_web_research(query:str):
        try:
            if PRIVATE_WEB_QUERY.search(query):
                reply='Tento dotaz může obsahovat přístupové údaje. Na veřejný web ho neodešlu.'
            else:
                await notify(ws,'thinking',text='Otevírám webové hledání, čtu výsledné stránky a ověřuji zdroje...')
                data=await asyncio.wait_for(asyncio.to_thread(full_web_research,query),timeout=110)
                cards=link_cards(data)
                if cards:
                    await notify(ws,'media',kind='search',items=cards,
                                 query=query,tool='web_search')
                reply=data['reply']
                msg='Zdroje jsou v galerii Jarvise'
                await notify(ws,'info',text='Web: '+str(data['evidence_level'])+' / '+msg)
        except Exception:
            reply='Webový průzkum nebylo možné dokončit nebo ověřit. Nevymyslel jsem žádné zdroje.'
        await notify(ws,'assistant',text=reply,speak=False)
        await notify(ws,'done')
    async def run_image_search(query:str):
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

    async def run_public_search(query:str):
        try:
            nonlocal recent_web_hits
            recent_web_hits=[]
            await notify(ws,'thinking',text='Vyhledávám veřejné odkazy přes DuckDuckGo Lite...')
            result=await asyncio.wait_for(asyncio.to_thread(live_web_search,query),timeout=19)
            recent_web_hits=list(result.get("results",[])[:6])
            reply=format_web_results(result)
            await notify(ws,'info',text='V2 web_search_public: reálné odkazy, neověřený obsah stránek')
        except (SearchUnavailable,ValueError,OSError,asyncio.TimeoutError):
            reply='Webové vyhledávání není dostupné nebo neposkytlo ověřitelné výsledky. Nic si nevymýšlím.'
        await notify(ws,'assistant',text=reply,speak=False)
        await notify(ws,'done')

    async def run_inspection(goal:str):
        try:
            await notify(ws,'thinking',text='Plánuji a ověřuji kroky: Git, Lua zdrojáky, izolované testy...')
            evidence=await asyncio.wait_for(asyncio.to_thread(inspect_project,goal),timeout=55)
            answer=format_inspection(evidence)
            await notify(ws,'info',text='V2 LangGraph: plán → čtecí nástroje → nezávislé ověření')
        except (RuntimeError,ValueError,OSError,asyncio.TimeoutError):
            answer='Kontrolní agent nedokončil ověření. Nic nebylo změněno ani označeno jako hotové.'
        await notify(ws,'assistant',text=answer,speak=False)
        await notify(ws,'done')

    async def run_code_search(symbol:str):
        try:
            await notify(ws,'thinking',text='Hledám Lua symbol v reálných zdrojových souborech ForeverRoute...')
            data=await asyncio.wait_for(asyncio.to_thread(search_lua,symbol),timeout=17)
            reply=format_code_search(data)
            await notify(ws,'info',text='V2 nástroj: foreverroute_lua_source_search / read-only')
        except (RuntimeError,ValueError,OSError,asyncio.TimeoutError):
            reply='Hledání ve zdrojovém kódu se nepodařilo ověřit. Nic jsem nezměnil.'
        await notify(ws,'assistant',text=reply,speak=False)
        await notify(ws,'done')

    async def run_repository_status():
        try:
            await notify(ws,'thinking',text='Čtu aktuální Git stav projektu ForeverRoute (pouze čtení)...')
            result=await asyncio.wait_for(asyncio.to_thread(get_repo_status),timeout=18)
            reply=format_repo_status(result)
            await notify(ws,'info',text='V2 nástroj: foreverroute_git_status / read-only')
        except (RuntimeError,OSError,asyncio.TimeoutError):
            reply='Aktuální Git stav se nepodařilo ověřit. Žádnou změnu jsem neprovedl.'
        await notify(ws,'assistant',text=reply,speak=False)
        await notify(ws,'done')

    async def run_general(prompt:str):
        try:
            await notify(ws,'thinking',text='Přemýšlím pomocí lokální AI; případně hledám v místních znalostech...')
            try:
                result=await asyncio.wait_for(
                    asyncio.to_thread(answer_general,prompt,list(chat_history),NOTES),timeout=65)
                reply=result['reply']
                chat_history.extend([{'role':'user','content':prompt},
                                     {'role':'assistant','content':reply}])
                del chat_history[:-8]
                await notify(ws,'info',text='RealJarvis 2.0: lokální konverzační model')
            except (LocalModelUnavailable,ValueError,asyncio.TimeoutError):
                reply='Lokální mozek teď neodpovídá. Zkontroluj, jestli běží Ollama. Žádná akce nebyla provedena.'
            await notify(ws,'assistant',text=reply,speak=False)
            await notify(ws,'done')
        except asyncio.CancelledError:
            raise

    async def run_strong(prompt:str):
        try:
            await notify(ws,'thinking',text='Zkouším existující bezplatný externí model, při selhání použiju lokální AI...')
            try:
                result=await asyncio.wait_for(
                    asyncio.to_thread(answer_strong,prompt,list(chat_history),NOTES),timeout=100)
                reply=result['reply']
                await notify(ws,'info',text='V2 model: '+result['status'])
            except Exception:
                reply='Externí model nebo místní záloha neodpověděly. Úkol nebyl proveden.'
            await notify(ws,'assistant',text=reply,speak=False)
            await notify(ws,'done')
        except asyncio.CancelledError:
            raise
    async def run_local(prompt:str):
        try:
            await notify(ws,'thinking',text='Odpovídá lokální Qwen; bez internetu a nástrojů...')
            try:
                result=await asyncio.wait_for(asyncio.to_thread(answer_local,prompt),timeout=60)
                reply='Experimentální lokální model, bez ověření a bez nástrojů:\n'+result
            except (LocalModelUnavailable,ValueError,asyncio.TimeoutError):
                reply='Lokální model neodpověděl spolehlivě. Úkol nebyl proveden.'
            await notify(ws,'assistant',text=reply,speak=False)
            await notify(ws,'done')
        except asyncio.CancelledError:
            raise
    async def run_grounded(question:str,kind:str):
        try:
            await notify(ws,'thinking',text='Ověřuji dokumentaci a připravuji podklady pro lokální model...')
            try:
                result=await asyncio.wait_for(asyncio.to_thread(answer_grounded,question,kind),timeout=62)
                reply=result['reply']
                await notify(ws,'info',text='V2 znalostní odpověď: '+result['status'])
            except Exception:
                reply='Znalostní model neodpověděl spolehlivě. Nic nebylo provedeno.'
            await notify(ws,'assistant',text=reply,speak=False)
            await notify(ws,'done')
        except asyncio.CancelledError:
            raise
    async def run_tool_training(stop_event):
        await notify(ws,'thinking',text='Ověřuji nástroje a ukládám postupy...')
        result=await asyncio.to_thread(train_all,advertised_tools=tools(),cancel_event=stop_event)
        await notify(ws,'assistant',text=training_report(result),speak=False)
        await notify(ws,'done')
    try:
        while True:
            msg=await ws.receive_json()
            typ=msg.get('type')
            if typ=='ping':await notify(ws,'pong');continue
            if typ=='cancel':
                if goal_task_id and active and not active.done():
                    await asyncio.to_thread(goal_cancel,goal_task_id)
                goal_task_id=None
                if taskid:ENG.cancel(taskid)
                if active and not active.done():active.cancel()
                active=None
                await notify(ws,'info',text='V2: požadavek zrušen')
                await notify(ws,'done');continue
            if typ=='confirm':
                await notify(ws,'info',text='V2: schvalování nástrojů pro zápis není aktivní.');continue
            if typ=='agent':
                await notify(ws,'info',text='V2 zatím nenabízí dalšího schváleného agenta.');continue
            if typ not in ('chat','command'):
                await notify(ws,'error',text='Neznámý typ požadavku.');await notify(ws,'done');continue
            text=str(msg.get('text') or msg.get('command') or '').strip()[:1200]
            if active and not active.done():
                if goal_task_id:await asyncio.to_thread(goal_cancel,goal_task_id)
                if taskid:ENG.cancel(taskid)
                active.cancel()
            active=None;taskid=None;goal_task_id=None
            if typ=='chat':await notify(ws,'user',text=text)
            if not text:await notify(ws,'done');continue
            if text.casefold() in ('stop','zastav','/stop','/cancel'):
                await notify(ws,'assistant',text='V2: žádný další úkol neběží.',speak=False)
                await notify(ws,'done');continue
            if text.casefold() in ('/help','pomoc'):
                await notify(ws,'assistant',text='RealJarvis 2.0: běžné otázky automaticky směruji do lokální AI. Zkus „Kolik je dva plus dva?“ nebo „Ověř Lua testy ForeverRoute“. Pro znalosti napiš „Znalosti: planner v4“. Pro paměť napiš „Zapamatuj si: ...“ a „Co si pamatuješ o ...?“. Pro lokální chat napiš „Lokálně: otázka“. Příkaz „Najdi ...“ spustí webový průzkum, otevře Edge a shrne přečtené zdroje. Pro bezplatný externí model s místní zálohou napiš „Silnější AI: otázka“. Pro odpověď se zdroji napiš „Zeptej se znalostí: otázka“. Pro web napiš „/web LangGraph Python documentation“, potom „/read 1“ pro přečtení prvního výsledku. Pro autonomní kontrolu napiš „Prověř chyby ForeverRoute v Lua funkci FR_NowNavRepeatsTitle“. Pro reálný stav projektu napiš „Zkontroluj Git ForeverRoute“. Další funkce zatím nejsou hotové.',speak=False)
                await notify(ws,'done');continue
            if msg.get('attachments'):
                await notify(ws,'assistant',text='V2 zatím nepodporuje přílohy; nic jsem nezpracoval.',speak=False)
                await notify(ws,'done');continue
            # Explicit goals are executed via the durable goal ledger, never
            # answered as read-only conversation or mistaken for capabilities.
            if text.casefold() in ('/ukoly','/úkoly','/goals'):
                rows=await asyncio.to_thread(goal_latest,7)
                text_out='\n'.join(x['id'][:8]+' '+x['status']+' '+x['goal'][:85] for x in rows)
                await notify(ws,'assistant',text=text_out or 'Zadne ulozene ukoly.',speak=False)
                await notify(ws,'done')
                continue
            if training_intent(text)=="run":active=asyncio.create_task(run_tool_training(threading.Event()));continue
            actionable=goal_extract(text)
            if actionable is not None:
                active=asyncio.create_task(run_action_goal(actionable))
                continue
            if training_intent(text)=="status":
                await notify(ws,"assistant",text=training_status_text(tool_learning_status()),speak=False)
                await notify(ws,"done")
                continue
            # Live and deterministic self-knowledge before model or action routing.
            self_knowledge=await asyncio.to_thread(capability_answer,text)
            if self_knowledge is not None:
                await notify(ws,'info',text='V2: live capability registry (read-only)')
                await notify(ws,'assistant',text=self_knowledge,speak=False)
                await notify(ws,'done')
                continue
            browser_action=browser_intent(text)
            if browser_action is not None:
                result=await asyncio.to_thread(browser_execute,browser_action)
                await notify(ws,'assistant',text=result['reply'],speak=False)
                await notify(ws,'done')
                continue
            internet_action=internet_intent(text)
            if internet_action is not None:
                active=asyncio.create_task(run_internet_command(internet_action))
                continue
            strong_prompt=extract_strong(text)
            if strong_prompt is not None:
                if not strong_prompt:
                    await notify(ws,'assistant',text='Za příkazem Silnější AI: napiš otázku. Dotaz se může odeslat externímu bezplatnému modelu.',speak=False)
                    await notify(ws,'done')
                else:
                    active=asyncio.create_task(run_strong(strong_prompt))
                continue
            local_prompt=extract_request(text)
            if local_prompt is not None:
                if not local_prompt:
                    await notify(ws,'assistant',text='Napiš /local a potom otázku.',speak=False)
                    await notify(ws,'done')
                else:
                    active=asyncio.create_task(run_local(local_prompt))
                continue
            grounded_request=extract_grounded_request(text)
            if grounded_request is not None:
                mode,question=grounded_request
                if not question:
                    await notify(ws,'assistant',text='Zadej za příkazem otázku k dokumentaci.',speak=False)
                    await notify(ws,'done')
                else:
                    active=asyncio.create_task(run_grounded(question,mode))
                continue
            if is_learning_question(text):
                reply=await asyncio.to_thread(learning_explain)
                await notify(ws,'assistant',text=reply,speak=False)
                await notify(ws,'done')
                continue
            image_request=image_query(text)
            if image_request is not None:
                active=asyncio.create_task(run_image_search(image_request))
                continue
            if project_study_intent(text):
                try:
                    await notify(ws,'thinking',text='Čtu skutečné soubory ForeverRoute...')
                    proof=await asyncio.wait_for(asyncio.to_thread(read_project_study,text),timeout=28)
                    reply=format_study(proof)
                    chat_history.extend([{'role':'user','content':text},{'role':'assistant','content':reply[:1800]}])
                    del chat_history[:-8]
                    await notify(ws,'info',text='Ověřená četba skutečného Git repozitáře ForeverRoute')
                except Exception:
                    reply='Zdroje ForeverRoute se nepodařilo kompletně ověřit; netvrdím, že jsem je prostudoval.'
                await notify(ws,'assistant',text=reply,speak=False)
                await notify(ws,'done')
                continue
            ordinary_web_query=extract_web_intent(text)
            if ordinary_web_query is not None:
                if not ordinary_web_query:
                    await notify(ws,'assistant',text='Co mám najít? Napiš například: Najdi oficiální manuál Lua 5.1.',speak=False)
                    await notify(ws,'done')
                else:
                    active=asyncio.create_task(run_web_research(ordinary_web_query))
                continue
            # Separate explicitly remembered user notes from cited documentation.
            try:
                note_reply=await asyncio.to_thread(handle_command,NOTES,text)
            except ValueError:
                note_reply='Poznámku jsem neuložil: neplatný formát.'
            except Exception:
                note_reply='Místní paměť právě není dostupná; nic jsem neuložil.'
            if note_reply is not None:
                await notify(ws,'assistant',text=note_reply,speak=False)
                await notify(ws,'done')
                continue
            read_index=extract_read_command(text)
            if read_index is not None:
                active=asyncio.create_task(run_page_read(read_index))
                continue
            web_query=extract_web_request(text)
            if web_query is not None:
                if not web_query:
                    await notify(ws,'assistant',text='Za /web zadej výraz k vyhledání.',speak=False)
                    await notify(ws,'done')
                else:
                    active=asyncio.create_task(run_public_search(web_query))
                continue
            symbol=extract_code_search(text)
            if symbol is not None:
                active=asyncio.create_task(run_code_search(symbol))
                continue
            if is_repo_status(text):
                active=asyncio.create_task(run_repository_status())
                continue
            kq=knowledge_query(text)
            if kq:
                answer=await asyncio.to_thread(knowledge.format_answer,kq)
                await notify(ws,'info',text='V2 znalosti: lokální dokumentace a citace')
                await notify(ws,'assistant',text=answer,speak=False)
                await notify(ws,'done')
                continue
            if is_inspection_goal(text):
                active=asyncio.create_task(run_inspection(text))
                continue
            kind=kind_from_text(text)
            if not kind:
                if unconnected_action(text):
                    await notify(ws,'assistant',text='Tuto funkci nové jádro zatím neumí. Původní Jarvis běží zvlášť; V2 nepředstírá úspěch.',speak=False)
                    await notify(ws,'done')
                else:
                    active=asyncio.create_task(run_general(text))
                continue
            active=asyncio.create_task(run_chat(text,kind))
    except WebSocketDisconnect:pass
    finally:
        if goal_task_id and active and not active.done():
            await asyncio.to_thread(goal_cancel,goal_task_id)
        if taskid and active and not active.done():
            ENG.cancel(taskid)
            active.cancel()

@app.get('/{path:path}')
def original_ui_fallback(path:str):
    target=(UI/path).resolve()
    if target.is_relative_to(UI.resolve()) and target.is_file():
        return FileResponse(target)
    return FileResponse(UI/'index.html',headers={'Cache-Control':'no-store'})






