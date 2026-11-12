"""Generic, evidence-first goal execution for isolated RealJarvis V2.

This is a bounded first-stage worker, NOT a model that can claim arbitrary work
was done. All tools are registered, read-only or write only to this module's
private task ledger/reports. No privileged commands or live project edits.
"""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import time
import unicodedata
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=ROOT/'goal_tasks.sqlite'
REPORTS=ROOT.parent/'reports'/'goals'
FINAL={'CHECKPOINT','BLOCKED_CAPABILITY','WAITING_APPROVAL','FAILED','INTERRUPTED','CANCELLED'}
_RISK=re.compile(r'\b(?:nainstal|stahni|smaz|vymaz|odstran|format|odinstal|zaplat|kup|objedn|publikuj|zverejni|nahraj na|rozesli|odesli|email|mail|zmen heslo|api klic|token|administrator|admin prava)\w*',re.I)
_ACTION=re.compile(
 r'^(?:(?:jarvisi|jarvis|prosim|prosím|ted|teď)\s*[, ]*\s*)*'
 r'(?:nauc se|uc se|ucis se|zlepsi|zdokonaluj|vylepsi|prostuduj|prozkoumej|'
 r'vytvor|vybuduj|naprogramuj|implementuj|oprav|vyres|zrealizuj|udelej|'
 r'zarid|pracuj na|optimalizuj|vyvijej|nainstaluj|stahni|vypracuj|'
 r'zkontroluj a oprav|nauc se pracovat|'
 r'chci aby ses|chci abys|mas za ukol|máš za úkol)\b',re.I)
_BLOCK_QUESTION=('jak ','proc ','proč ','co ','kdy ','kde ','je mozne','je možné',
                 'muzete ','muzes ','můžeš ','dokazes ','dokážeš ','umel bys ','uměl bys ')

def norm(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',str(text).casefold())
                            if not unicodedata.combining(c)).split())

def extract_goal(text):
    """Only explicit action goals; never treat ordinary questions as commands."""
    if not isinstance(text,str) or not (8<=len(text.strip())<=1200):
        return None
    raw=text.strip()
    # Dedicated allowlisted tool-learning stays in charge of self-tool-study goals.
    try:
        from tool_learning import training_intent
        if training_intent(raw)=='run':return None
    except (ImportError,ValueError):pass
    n=norm(raw)
    if any(n.startswith(x) for x in _BLOCK_QUESTION) or raw.rstrip().endswith('?'):
        return None
    if not _ACTION.match(n) and not (n.startswith('zjisti ') and
            any(x in n for x in (' a nauc se',' a oprav',' a pouzij',' a zrealizuj'))):
        return None
    return raw

def category(goal):
    n=norm(goal)
    if any(x in n for x in ('cesk','cest','jazyk','gramatik','slovnik','vyslovnost')):
        return 'czech'
    if any(x in n for x in ('hlas','tts','mikrofon','stt','mluven','rec','poslouch')):
        return 'voice'
    if any(x in n for x in ('foreverroute','addon','planner','quest','lua')):
        return 'foreverroute'
    if any(x in n for x in ('pamet','uceni','zkušenost','zkusenost')):
        return 'memory'
    if any(x in n for x in ('nastroj','schopnost','co mas k dispozici','vybaven','moznost')):
        return 'capabilities'
    return 'general'

def risk(goal):
    return bool(_RISK.search(norm(goal)))

def conn():
    DB.parent.mkdir(parents=True,exist_ok=True)
    cx=sqlite3.connect(DB,timeout=12)
    cx.execute('PRAGMA busy_timeout=12000')
    cx.execute('CREATE TABLE IF NOT EXISTS goals(id TEXT PRIMARY KEY, body TEXT NOT NULL, updated REAL NOT NULL)')
    cx.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, state TEXT NOT NULL, detail TEXT, at REAL NOT NULL)')
    cx.commit()
    return cx

def record(cx,task,detail):
    cx.execute('UPDATE goals SET body=?,updated=? WHERE id=?',
               (json.dumps(task,ensure_ascii=False),time.time(),task['id']))
    cx.execute('INSERT INTO events(task_id,state,detail,at) VALUES(?,?,?,?)',
               (task['id'],task['status'],detail[:300],time.time()))

def create(goal):
    if extract_goal(goal) is None:raise ValueError('Not an actionable goal')
    task={'id':str(uuid.uuid4()),'goal':goal.strip(),'category':category(goal),
          'status':'QUEUED','created_at':int(time.time()),'stage':0,
          'evidence':{},'completed_steps':[],'next_step':'Provest pocatecni audit',
          'report_path':None,'requires_approval':risk(goal)}
    with conn() as cx:
        cx.execute('INSERT INTO goals(id,body,updated) VALUES(?,?,?)',
                   (task['id'],json.dumps(task,ensure_ascii=False),time.time()))
        cx.execute('INSERT INTO events(task_id,state,detail,at) VALUES(?,?,?,?)',
                   (task['id'],'QUEUED','Task accepted, no action yet',time.time()))
    return task

def get(task_id):
    with conn() as cx:
        row=cx.execute('SELECT body FROM goals WHERE id=?',(task_id,)).fetchone()
    if row is None:raise KeyError(task_id)
    return json.loads(row[0])

def latest(limit=8):
    with conn() as cx:
        rows=cx.execute('SELECT body FROM goals ORDER BY updated DESC LIMIT ?',
                        (max(1,min(int(limit),30)),)).fetchall()
    return [json.loads(row[0]) for row in rows]

def _safe_inventory():
    from capability_inventory import inventory
    data=inventory(probe=True)
    return {'tts_bridge':bool(data['tts_connected_to_v2']),
            'web_tools':bool(data['web_tools_installed']),
            'code_tools':bool(data['code_tools_installed']),
            'notes_db':bool(data['notes_db_present']),
            'voice':data['tts_external_service'],
            'capability_domains':sorted(data['features'])}

def _language_audit():
    from in_app_media import image_query
    from behavior_router import extract_web_intent
    nouns=('kocek','psu','kachnicek','aut','kvetin','stromu','hor','hradů','mostu',
           'letadel','domu','knih','telefonu','planet','moru','ptaku','mestecek',
           'krajiny','vlaku','receptu','psu na snehu','ceskych pamatek')
    image_prefixes=('Najdi obrazky','Najdi mi obrazky','Ukaz fotky',
                    'Zobraz fotografie','Vyhledej obrazky','Hledej fotky',
                    'Najfi obrazky','Jarvisi, najdi obrazky')
    web_prefixes=('Najdi informace o','Dohledej podrobnosti o',
                  'Vyhledej informace o','Hledej navody k')
    tested=0; failed=[]; fail_count=0
    def probe(kind,utterance,passed):
        nonlocal tested,fail_count
        tested+=1
        if not passed:
            fail_count+=1
            if len(failed)<28:failed.append({'kind':kind,'utterance':utterance})
    for noun in nouns:
        for phrase in image_prefixes:
            utterance=phrase+' '+noun
            expected=norm(noun)
            actual=image_query(utterance)
            probe('image_search',utterance,actual==expected)
    for noun in nouns[:12]:
        for phrase in web_prefixes:
            utterance=phrase+' '+noun
            probe('web_search',utterance,extract_web_intent(utterance) is not None)
    for noun in nouns[:12]:
        for local in ('Najdi na disku ','Najdi v souborech '):
            utterance=local+noun
            probe('local_not_web',utterance,extract_web_intent(utterance) is None)
    for question in ('Ahoj','Jak se mas?','Co umis?','Kdy budes hotovy?',
                     'Oprav si hlas','Nauc se cesky','Umis vysvetlit fyziku?',
                     'Kolik je dva plus dva?','Prosim porad mi','Dekuji'):
        probe('non_media',question,image_query(question) is None)
    return {'test_scope':'Czech command routing, NOT Czech fluency or model retraining',
            'total':tested,'passed':tested-fail_count,
            'failure_examples':failed,'failure_count':fail_count,'failure_examples_capped':fail_count>28,
            'model_weights_retrained':False,'sources':'in_app_media + behavior_router',
            'sample_digest_sha256':hashlib.sha256('|'.join(image_prefixes+nouns).encode('utf-8')).hexdigest()}

def _voice_audit():
    state=_safe_inventory()
    src=(ROOT/'ui_compat.py').read_text(encoding='utf-8-sig')
    return {'tts_backend':state['voice'],'tts_http_bridge':state['tts_bridge'],
            'assistant_explicit_speak_false_count':len(re.findall(r"notify\(ws,'assistant'.*speak=False",src)),
            'stt_live_verified':False,
            'output_really_played_verified':False,
            'scope':'status endpoint and static source inspection; no sound was played'}

def _project_audit():
    from project_tools import status
    return {'git_status':status(),'no_project_writes':True}

def _memory_audit():
    from experience_learning import summary
    data=summary()
    data['model_weights_retrained']=False
    return data

REGISTRY={'czech':_language_audit,'voice':_voice_audit,
          'foreverroute':_project_audit,'memory':_memory_audit,
          'capabilities':_safe_inventory,'general':_safe_inventory}
NEXT={
 'czech':'Z výsledků sestavit opravy porozumění a po schválení bezpečně otestovat; test příkazů neprokazuje plynulou češtinu.',
 'voice':'Zprovoznit označení speak:true pouze u finální odpovědi, následně nezávisle ověřit slyšitelné přehrávání a mikrofon.',
 'foreverroute':'Stanovit konkrétní chybu, vytvořit oddělený patch s testy; do živé databáze ani freeze gate nezasahovat.',
 'memory':'Navrhnout konkrétní měřitelnou paměťovou úlohu, ověřit přenos zkušeností bez měnění vah modelu.',
 'capabilities':'Vybrat nepropojené schopnosti, ověřit jejich rozhraní izolovanými testy.',
 'general':'Chybí bezpečný prováděcí nástroj pro tuto kategorii. Potřebuji konkrétní scope a autorizovaný plugin.'
}

def run(task_id):
    with conn() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT body FROM goals WHERE id=?',(task_id,)).fetchone()
        if not row:raise KeyError(task_id)
        task=json.loads(row[0])
        if task['status']!='QUEUED':return task
        task['status']='RUNNING'
        record(cx,task,'Claimed task; starting bounded safe probe')
    try:
        if task['requires_approval']:
            evidence={'reason':'Sensitive or potentially destructive/public/spending action; not executed'}
            state='WAITING_APPROVAL'
            next_step='Před změnou oprávnění, nákupem, publikací či destruktivním krokem je nutné konkrétní schválení.'
        else:
            fn=REGISTRY[task['category']]
            evidence=fn()
            state='BLOCKED_CAPABILITY' if task['category']=='general' else 'CHECKPOINT'
            next_step=NEXT[task['category']]
        report={'task_id':task_id,'goal':task['goal'],'category':task['category'],
                'status':state,'verified_stage':'initial bounded diagnostic',
                'evidence':evidence,'next_step':next_step,
                'note':'This is not proof the overall goal is finished.',
                'time_utc_epoch':int(time.time())}
        REPORTS.mkdir(parents=True,exist_ok=True)
        dest=REPORTS/(task_id+'.json')
        dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        task.update(status=state,evidence=evidence,stage=1,report_path=str(dest),
                    next_step=next_step,
                    completed_steps=['Bezpečný úvodní audit s uloženými důkazy'])
    except Exception as exc:
        task.update(status='FAILED',next_step='Diagnostika selhala; ověřit nástroj.',
                    evidence={'error_type':type(exc).__name__},stage=0)
    with conn() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT body FROM goals WHERE id=?',(task_id,)).fetchone()
        if row and json.loads(row[0]).get('status')=='CANCELLED':
            return json.loads(row[0])
        record(cx,task,'Bounded diagnostic finished, evidence saved')
    return task

def cancel(task_id):
    with conn() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT body FROM goals WHERE id=?',(task_id,)).fetchone()
        if not row:raise KeyError(task_id)
        task=json.loads(row[0])
        if task['status'] in FINAL and task['status']!='CHECKPOINT':return task
        task['status']='CANCELLED'
        task['next_step']='Zrušeno uživatelem; žádný další krok není naplánován.'
        record(cx,task,'User cancelled')
    return task

def recover_stale(seconds=180):
    # On restart, never silently rerun orphaned actions.
    with conn() as cx:
        cx.execute('BEGIN IMMEDIATE')
        rows=cx.execute('SELECT id,body,updated FROM goals').fetchall()
        count=0
        for task_id,raw,updated in rows:
            task=json.loads(raw)
            if task['status']=='RUNNING' and updated<time.time()-seconds:
                task['status']='INTERRUPTED'
                task['next_step']='Nedokončený krok musí být ověřen před opakováním.'
                record(cx,task,'Recovered orphan; no automatic retry')
                count+=1
        return count

def format_result(task):
    ev=task.get('evidence') or {}
    suffix=''
    if task['category']=='czech' and task['status']=='CHECKPOINT':
        suffix=f" Testy rozpoznávání českých příkazů: {ev.get('passed')}/{ev.get('total')} (nejde o hodnocení plynulosti)."
    if task['category']=='voice' and task['status']=='CHECKPOINT':
        suffix=f" TTS backend dostupný: {ev.get('tts_backend',{}).get('ready')}; přehrání a mikrofon dosud neověřeny."
    return (f"Úkol {task['id'][:8]} | {task['status']}. "
            f"První fáze: "+('provedený audit s důkazy.' if task['status']=='CHECKPOINT' else 'nebyla potvrzena jako dokončený cíl.')
            +suffix+f"\nDalší krok: {task['next_step']}"
            +(f"\nDůkaz: {task['report_path']}" if task.get('report_path') else ''))

