"""Isolated RealJarvis V2 state graph. No production actions or model calls."""
from __future__ import annotations
from typing import TypedDict
from contextlib import contextmanager
from pathlib import Path
import hashlib,json,re,sqlite3,subprocess,time,uuid
from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.sqlite import SqliteSaver

ROOT=Path(__file__).resolve().parent.parent
LUA=Path(r'C:\Users\Dawis\AppData\Local\Temp\lua51\lua5.1.exe')
FIXTURE=ROOT/'OpenCodeLuaPilot'
KINDS={'arithmetic','lua_audit','coding_proposal'}
TERMINAL={'VERIFIED','FAILED','CANCELLED','INTERRUPTED'}

class State(TypedDict,total=False):
    id:str
    goal:str
    kind:str
    approved:bool
    status:str
    answer:str
    evidence:dict
    error:str

def digest(file:Path)->str:
    return hashlib.sha256(file.read_bytes()).hexdigest()

class TaskStore:
    def __init__(self,path:Path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, state_json TEXT NOT NULL, updated REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, state TEXT NOT NULL, time REAL NOT NULL)')
    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=12)
        db.execute('PRAGMA busy_timeout=12000')
        try:
            yield db
            db.commit()
        finally:
            db.close()
    def save(self,s:State):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT state_json FROM tasks WHERE id=?',(s['id'],)).fetchone()
            if row and json.loads(row[0]).get('status') in TERMINAL:
                return
            db.execute('INSERT OR REPLACE INTO tasks(id,state_json,updated) VALUES(?,?,?)',(s['id'],json.dumps(s,ensure_ascii=False),time.time()))
            db.execute('INSERT INTO events(task_id,state,time) VALUES(?,?,?)',(s['id'],s['status'],time.time()))
    def claim(self,task_id:str):
        """Atomic claim: never execute the same task concurrently."""
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT state_json FROM tasks WHERE id=?',(task_id,)).fetchone()
            if not row: raise KeyError(task_id)
            s=json.loads(row[0])
            if s['status']!='PLANNED' and not (s['status']=='WAITING_APPROVAL' and s.get('approved')):
                return False,s
            s={**s,'status':'RUNNING','started_at':time.time()}
            db.execute('UPDATE tasks SET state_json=?,updated=? WHERE id=?',
                       (json.dumps(s,ensure_ascii=False),time.time(),task_id))
            db.execute('INSERT INTO events(task_id,state,time) VALUES(?,?,?)',
                       (task_id,'RUNNING',time.time()))
            return True,s

    def recover_stale(self,grace_seconds:float=120)->int:
        """Conservatively mark expired orphan jobs INTERRUPTED; never rerun writes."""
        if grace_seconds<30: raise ValueError('Grace period must be >=30s')
        cutoff=time.time()-grace_seconds
        count=0
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for task_id,raw,updated in db.execute(
                "SELECT id,state_json,updated FROM tasks").fetchall():
                s=json.loads(raw)
                if s.get('status')!='RUNNING': continue
                if float(s.get('started_at',updated))>cutoff: continue
                s={**s,'status':'INTERRUPTED','error':'stale_worker','answer':'Prace byla prerusena; nebyla overena.'}
                db.execute('UPDATE tasks SET state_json=?,updated=? WHERE id=?',
                           (json.dumps(s,ensure_ascii=False),time.time(),task_id))
                db.execute('INSERT INTO events(task_id,state,time) VALUES(?,?,?)',
                           (task_id,'INTERRUPTED',time.time()))
                count+=1
        return count

    def get(self,id:str)->State:
        with self.connection() as db:
            row=db.execute('SELECT state_json FROM tasks WHERE id=?',(id,)).fetchone()
        if not row: raise KeyError(id)
        return json.loads(row[0])

def authorize(s:State)->State:
    if s.get('status')=='CANCELLED':return s
    if s['kind'] not in KINDS:
        return {**s,'status':'FAILED','error':'kind_not_allowed'}
    if s['kind']=='coding_proposal' and not s.get('approved',False):
        return {**s,'status':'WAITING_APPROVAL','answer':'Kódový agent zatím nemá povolení.'}
    return {**s,'status':'RUNNING'}

def do_work(s:State,store:TaskStore|None=None)->State:
    if s['kind']=='arithmetic':
        words=s.get('goal','').lower()
        if re.search(r'\b(2\s*\+\s*2|dva\s+plus\s+dva)\b',words):
            return {**s,'answer':'Dva plus dva jsou čtyři.','evidence':{'operation':'2+2','value':4}}
        return {**s,'status':'FAILED','error':'unsupported_calculation'}
    if s['kind']=='coding_proposal':
        return {**s,'status':'FAILED','error':'coding_agent_not_connected','answer':'Agent musí nejdříve projít izolovaným testem.'}
    test=FIXTURE/'tests'/'now_card_objectives.lua'
    lua_file=FIXTURE/'ForeverRoute_UIv2.lua'
    if not (test.is_file() and lua_file.is_file() and LUA.is_file()):
        return {**s,'status':'FAILED','error':'fixture_missing'}
    before=(digest(test),digest(lua_file))
    try:
        p=subprocess.Popen([str(LUA),str(test),str(FIXTURE)],cwd=FIXTURE,
                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                 text=True,encoding='utf-8',errors='replace')
        deadline=time.monotonic()+18
        while True:
            try:
                stdout,stderr=p.communicate(timeout=0.08)
                break
            except subprocess.TimeoutExpired:
                if store and store.get(s['id']).get('status')=='CANCELLED':
                    p.kill()
                    p.communicate()
                    return {**s,'status':'CANCELLED','answer':'Ukol zrusen; testovaci proces zastaven.','error':'cancelled'}
                if time.monotonic()>deadline:
                    p.kill()
                    p.communicate()
                    return {**s,'status':'FAILED','error':'lua_test_timeout','answer':'Lua test prekrocil 18 s.'}
    except (OSError,subprocess.SubprocessError) as e:
        return {**s,'status':'FAILED','error':type(e).__name__}
    unchanged=before==(digest(test),digest(lua_file))
    output=stdout[-900:]
    return {**s,'evidence':{'test_sha256':before[0],'code_sha256':before[1],
                'unchanged':unchanged,'exit_code':p.returncode,'test_output':output},
             'answer':output.strip().splitlines()[-1] if output.strip() else '',
             'status':'RUNNING' if unchanged else 'FAILED',
             'error':'' if unchanged else 'source_or_tests_mutated'}

def verify(s:State)->State:
    if s.get('status') in TERMINAL:return s
    if s.get('status')=='WAITING_APPROVAL':return s
    if s['kind']=='arithmetic':
        good=s.get('evidence',{}).get('value')==4 and 'čtyři' in s.get('answer','')
    elif s['kind']=='lua_audit':
        ev=s.get('evidence',{})
        good=(ev.get('exit_code')==0 and ev.get('unchanged') and '72 checks, 0 failures' in ev.get('test_output',''))
    else:good=False
    return {**s,'status':'VERIFIED' if good else 'FAILED',
            'error':'' if good else (s.get('error') or 'independent_test_failed')}

def make_graph(store:TaskStore|None=None,checkpointer=None):
    g=StateGraph(State)
    g.add_node('authorize',authorize)
    g.add_node('execute',lambda s:do_work(s,store))
    g.add_node('verify',verify)
    g.add_edge(START,'authorize')
    g.add_conditional_edges('authorize',lambda s:'execute' if s['status']=='RUNNING' else 'verify',
                            {'execute':'execute','verify':'verify'})
    g.add_edge('execute','verify')
    g.add_edge('verify',END)
    return g.compile(checkpointer=checkpointer)

class Engine:
    def __init__(self,db_path:Path):
        self.store=TaskStore(db_path)
        self.recovered_interrupted=self.store.recover_stale(120)
        self.graph=make_graph(self.store)
    def create(self,kind:str,goal:str,approved:bool=False)->State:
        if not kind or not isinstance(goal,str) or not 1<=len(goal)<=1200:raise ValueError('Invalid task')
        s:State={'id':str(uuid.uuid4()),'kind':kind,'goal':goal,
                 'approved':bool(approved),'status':'PLANNED','answer':'','evidence':{},'error':''}
        self.store.save(s)
        return s
    def cancel(self,task_id:str)->State:
        s=self.store.get(task_id)
        if s['status'] in TERMINAL:return s
        s['status']='CANCELLED';s['answer']='Úkol zrušen.'
        self.store.save(s)
        return self.store.get(task_id)
    def approve(self,task_id:str)->State:
        s=self.store.get(task_id)
        if s['status']!='WAITING_APPROVAL':raise ValueError('Not waiting for approval')
        s['approved']=True
        self.store.save(s)
        return s
    def recover_stale(self,grace_seconds:float=120)->int:
        return self.store.recover_stale(grace_seconds)

    def run(self,task_id:str)->State:
        claimed,s=self.store.claim(task_id)
        if not claimed:return s
        last=None
        try:
            checkdb=str(self.store.path.with_suffix('.graph.sqlite'))
            with SqliteSaver.from_conn_string(checkdb) as saver:
                graph=make_graph(self.store,checkpointer=saver)
                config={'configurable':{'thread_id':task_id}}
                for current in graph.stream(s,config=config,stream_mode='values'):
                    if current!=last:
                        self.store.save(current)
                    last=current
        except Exception as e:
            self.store.save({**s,'status':'FAILED','error':'engine_exception:'+type(e).__name__})
        return self.store.get(task_id)

if __name__=='__main__':
    engine=Engine(ROOT/'BrainCore'/'tasks.sqlite')
    for kind,goal in [('arithmetic','Kolik je dva plus dva?'),('lua_audit','Ověř 72 Lua testů v izolaci'),
                      ('coding_proposal','Oprav ForeverRoute Lua')]:
        s=engine.create(kind,goal)
        result=engine.run(s['id'])
        print(json.dumps({'id':result['id'],'kind':kind,'status':result['status'],
                          'answer':result.get('answer'),'error':result.get('error')},ensure_ascii=True))
