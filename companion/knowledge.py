"""Read-only source-cited local knowledge for RealJarvis V2."""
from pathlib import Path
from contextlib import contextmanager
import hashlib,re,sqlite3,sys,threading
ROOT=Path(__file__).resolve().parent.parent
REPO=Path(r'H:\RealJarvis\AgentTeam\ForeverRouteDev')
DB=ROOT/'BrainCore'/'knowledge.sqlite'
INBOX=ROOT/'KnowledgeInbox'
_REFRESH_LOCK=threading.RLock()
ROOT_NAMES={'README.md','DEVELOPMENT.md','IN_GAME_TEST_CHECKLIST.md',
    'REAL_CLIENT_VALIDATION.md','THIRD_PARTY_DATA.md'}
BANNED=re.compile(r'(?i)(secret|credential|token|password|private[_-]?key|api[_-]?key|\.env|\.pem)')
STOP={'co','mi','je','to','a','o','ve','v','na','jak','jaky','jake','jaka','pro','ze',
      'se','the','and','how','what','do','of','or','an','with','about','kde','vime','vis'}

@contextmanager
def db():
    DB.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(DB,timeout=12)
    try:yield conn;conn.commit()
    finally:conn.close()
def sources():
    files=[REPO/n for n in ROOT_NAMES]
    files+=sorted(REPO.glob('RELEASE_NOTES_*.md'))
    for d in (REPO/'docs',REPO/'wiki'):
        if d.is_dir():
            files+=sorted(p for p in d.rglob('*') if p.suffix.lower() in {'.md','.txt'})
    files.append(ROOT/'README.md')
    files.append(ROOT/'JARVIS_PROVOZNI_MANUAL_V3.txt')
    files.append(ROOT/'JARVIS_PROVOZNI_MANUAL_V4.txt')
    if INBOX.is_dir():
        files.extend(sorted(p for p in INBOX.glob('*') if p.suffix.lower() in ('.md','.txt') and not p.name.startswith('.')))
    seen=set()
    for p in files:
        try:
            if not p.is_file() or p.is_symlink() or BANNED.search(p.name) or p.stat().st_size>175000:continue
            real=p.resolve()
            if real in seen:continue
            if not (real.is_relative_to(REPO.resolve()) or real in ((ROOT/'README.md').resolve(),(ROOT/'JARVIS_PROVOZNI_MANUAL_V3.txt').resolve(),(ROOT/'JARVIS_PROVOZNI_MANUAL_V4.txt').resolve()) or real.parent==INBOX.resolve()):continue
            seen.add(real)
            yield p
        except (OSError,ValueError):continue

def blocks(text):
    lines=text.splitlines()
    start=1;piece=[];length=0
    for idx,line in enumerate(lines,1):
        if length+len(line)>1200 and piece:
            yield start,'\n'.join(piece)
            start=idx;piece=[];length=0
        if not piece:start=idx
        piece.append(line[:1200]);length+=len(line[:1200])+1
    if piece:yield start,'\n'.join(piece)
def source_fingerprint():
    """Fast fingerprint of explicitly permitted documents, not a content dump."""
    h=hashlib.sha256()
    for p in sources():
        try:
            stat=p.stat()
            label=str(p.resolve()).casefold()
            h.update((label+'\0'+str(stat.st_size)+'\0'+str(stat.st_mtime_ns)+'\n').encode('utf-8'))
        except OSError:continue
    return h.hexdigest()
def build_index():
    total=0;docs=0
    with db() as cx:
        cx.execute('CREATE TABLE IF NOT EXISTS kb_meta (key TEXT PRIMARY KEY, val TEXT)')
        cx.execute('CREATE VIRTUAL TABLE IF NOT EXISTS kb USING fts5(source UNINDEXED, line UNINDEXED, title, body, tokenize="unicode61 remove_diacritics 2")')
        cx.execute('DELETE FROM kb')
        for file in sources():
            try:text=file.read_text(encoding='utf-8-sig')
            except (UnicodeError,OSError):continue
            if '\x00' in text:continue
            title=next((x.strip('# ').strip() for x in text.splitlines()[:25] if x.lstrip().startswith('#')),file.stem)
            rel= ('ForeverRoute/'+file.relative_to(REPO).as_posix()
                  if file.is_relative_to(REPO) else ('KnowledgeInbox/'+file.name if file.is_relative_to(INBOX) else 'RealJarvis2/'+file.name))
            docs+=1
            for line,body in blocks(text):
                if len(body.strip())<18:continue
                cx.execute('INSERT INTO kb(source,line,title,body) VALUES (?,?,?,?)',
                           (rel,line,title[:130],body))
                total+=1
        cx.execute('INSERT OR REPLACE INTO kb_meta(key,val) VALUES (?,?)',('documents',str(docs)))
        cx.execute('INSERT OR REPLACE INTO kb_meta(key,val) VALUES (?,?)',('chunks',str(total)))
        cx.execute('INSERT OR REPLACE INTO kb_meta(key,val) VALUES (?,?)',('fingerprint',source_fingerprint()))
    return {'documents':docs,'chunks':total}

def status():
    if not DB.exists():return {'ready':False,'documents':0,'chunks':0}
    with db() as cx:
        try:
            x=dict(cx.execute('SELECT key,val FROM kb_meta').fetchall())
            return {'ready':True,'documents':int(x.get('documents','0')),'chunks':int(x.get('chunks','0')),'stale':x.get('fingerprint','')!=source_fingerprint()}
        except sqlite3.OperationalError:return {'ready':False,'documents':0,'chunks':0}
def refresh_if_needed():
    """Refresh stale document index on demand; safe across threads."""
    with _REFRESH_LOCK:
        snapshot=status()
        if not snapshot.get('ready',False) or snapshot.get('stale',True):
            return build_index()
        return None
def focused_excerpt(body,terms):
    line=' '.join(body.split())
    offset=0
    for term in terms:
        if term in ('foreverroute','beta'):continue
        m=re.search(r'(?<!\w)'+re.escape(term)+r'\w*',line,re.IGNORECASE)
        if m:
            offset=max(0,m.start()-75)
            break
    out=line[offset:offset+440]
    if offset:out='…'+out
    if offset+440<len(line):out+='…'
    return out
def search(question:str,limit:int=4):
    if not isinstance(question,str) or not 1<=len(question.strip())<=250:return []
    refresh_if_needed()
    tokens=[v for v in re.findall(r'[^\W_]+',question.casefold(),flags=re.UNICODE) if len(v)>1 and v not in STOP]
    if not tokens:return []
    expansions={'levely':['levels','level'],'levelu':['levels','level'],
      'urovne':['levels','level'],'questy':['quests','quest'],
      'questu':['quests','quest'],'ukoly':['quests','quest'],
      'planovac':['planner'],'planovacv4':['planner','v4'],
      'routy':['route','routes'],'trasu':['route','routes'],
      'dokumentace':['docs'],'pokrývá':['covers','levels'],
      'beta':['beta']}
    expanded=[]
    for v in tokens:
        expanded.append(v)
        expanded+=expansions.get(v,[])
    terms=list(dict.fromkeys(expanded))[:12]
    expr=' OR '.join('"'+word+'"*' for word in terms)
    with db() as cx:
        try:
            rows=cx.execute('SELECT source,line,title,body FROM kb WHERE kb MATCH ? ORDER BY bm25(kb,0,0,4,1) LIMIT ?',
                            (expr,max(20,min(limit*18,90)))).fetchall()
        except sqlite3.OperationalError:return []
    output=[]
    for source,line,title,body in rows:
        excerpt=focused_excerpt(body,terms)
        output.append({'source':source,'line':int(line),'title':title,'excerpt':excerpt})
    # Current documentation outranks historical release notes unless the user asks
    # about a specific beta explicitly. Do not silently mix beta1 with latest.
    for hit in output:
        hit['scope']='historical_release' if '/RELEASE_NOTES_' in hit['source'] else ('user_supplied' if hit['source'].startswith('KnowledgeInbox/') else 'project_docs')
    explicit_version=bool(re.search(r'\bbeta[\s.\-_]*\d',question,re.IGNORECASE))
    if not explicit_version:
        coverage=any(v in question.casefold() for v in ('levely','levelu','levels','urovn','pokr'))
        output.sort(key=lambda hit:(hit['scope']=='historical_release',0 if coverage and hit['source']=='ForeverRoute/README.md' else 1))
    return output[:max(1,min(limit,8))]

def format_answer(question:str)->str:
    hits=search(question,limit=3)
    if not hits:return 'V místní znalostní bázi jsem k tomuto dotazu nenašel podklad. Nebudu odpověď vymýšlet.'
    parts=['Našel jsem tyto pasáže v místní dokumentaci (pouze výňatky, nikoli ověřený závěr AI):']
    for i,item in enumerate(hits,1):
        parts.append(f"{i}. {item['title']} — {item['source']}:{item['line']}\n{item['excerpt'][:300]}")
    return '\n\n'.join(parts)

if __name__=='__main__':
    import json
    mode=sys.argv[1] if len(sys.argv)>1 else 'status'
    if mode=='index':print(json.dumps(build_index(),ensure_ascii=True))
    elif mode=='search':print(json.dumps(search(' '.join(sys.argv[2:])),ensure_ascii=True))
    else:print(json.dumps(status(),ensure_ascii=True))
