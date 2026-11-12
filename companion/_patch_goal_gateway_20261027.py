"""One-time, guarded V2GoalFlow wiring. Abort on concurrent changes."""
from pathlib import Path
import ast
import shutil
p=Path(r'H:\RealJarvis\V2Sandbox\BrainCore\ui_compat.py')
initial=p.read_bytes()
s=initial.decode('utf-8-sig')
nl='\r\n' if s.count('\r\n')>s.count('\n')//2 else '\n'
def replace_once(a,b):
    global s
    assert s.count(a)==1,(a,s.count(a))
    s=s.replace(a,b,1)
def n(text):
    return text.replace('\n',nl)

replace_once('from task_engine import Engine,ROOT',
 n("""from task_engine import Engine,ROOT
from goal_workflow import (create as goal_create,run as goal_run,
     extract_goal as goal_extract,format_result as goal_format,
     latest as goal_latest,get as goal_get,cancel as goal_cancel,
     recover_stale as goal_recover)"""))

replace_once("@app.api_route('/api/{path:path}',methods=['GET','POST','PUT','PATCH','DELETE'])",
 n("""@app.get('/api/goals')
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

@app.api_route('/api/{path:path}',methods=['GET','POST','PUT','PATCH','DELETE'])"""))

replace_once("    taskid:str|None=None",
             n("""    taskid:str|None=None
    goal_task_id:str|None=None"""))
replace_once("    async def run_chat(text:str,kind:str):",n("""    async def run_action_goal(goal:str):
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

    async def run_chat(text:str,kind:str):"""))

replace_once("            if typ=='cancel':",n("""            if typ=='cancel':
                if goal_task_id and active and not active.done():
                    await asyncio.to_thread(goal_cancel,goal_task_id)
                goal_task_id=None"""))

replace_once("            if active and not active.done():\n                if taskid:ENG.cancel(taskid)",
             n("""            if active and not active.done():
                if goal_task_id:await asyncio.to_thread(goal_cancel,goal_task_id)
                if taskid:ENG.cancel(taskid)"""))

replace_once("            active=None;taskid=None",n("""            active=None;taskid=None;goal_task_id=None"""))

replace_once("            # Live and deterministic self-knowledge before model or action routing.",
 n("""            # Explicit goals are executed via the durable goal ledger, never
            # answered as read-only conversation or mistaken for capabilities.
            if text.casefold() in ('/ukoly','/úkoly','/goals'):
                rows=await asyncio.to_thread(goal_latest,7)
                text_out='\\n'.join(x['id'][:8]+' '+x['status']+' '+x['goal'][:85] for x in rows)
                await notify(ws,'assistant',text=text_out or 'Zadne ulozene ukoly.',speak=False)
                await notify(ws,'done')
                continue
            actionable=goal_extract(text)
            if actionable is not None:
                active=asyncio.create_task(run_action_goal(actionable))
                continue
            # Live and deterministic self-knowledge before model or action routing."""))

replace_once("    finally:\n        if taskid and active and not active.done():",
 n("""    finally:
        if goal_task_id and active and not active.done():
            await asyncio.to_thread(goal_cancel,goal_task_id)
        if taskid and active and not active.done():"""))

ast.parse(s)
assert p.read_bytes()==initial,'Concurrent change: refusing overwrite'
bak=p.with_name('ui_compat.py.before_goal_workflow_20261027.bak')
assert not bak.exists(),'Backup already exists'
shutil.copy2(p,bak)
p.write_bytes(s.encode('utf-8'))
print('GOAL_PATCH_APPLIED',len(initial),len(s.encode('utf-8')))

