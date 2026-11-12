"""Local, explicit user-note memory for isolated RealJarvis V2."""
from __future__ import annotations
import re,sqlite3,time,uuid
from contextlib import contextmanager
from pathlib import Path

STOP={'co','si','o','to','ze','že','mi','je','a','v','na','do','pro','od','z','se','pamatujes','pamatuješ','vis','víš','jak','mam','mám','prosim','prosím','pripomen','připomeň'}
def words(s):
    return [t for t in re.findall(r'[^\W_]+',s.casefold()) if len(t)>2 and t not in STOP]

class NoteStore:
    def __init__(self,path:Path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.open() as db:
            db.execute('CREATE TABLE IF NOT EXISTS notes (id TEXT PRIMARY KEY, content TEXT NOT NULL, normalized TEXT NOT NULL UNIQUE, origin TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL)')
    @contextmanager
    def open(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.execute('PRAGMA busy_timeout=10000')
        try:
            yield db
            db.commit()
        finally:
            db.close()
    def remember(self,content:str):
        if not isinstance(content,str): raise ValueError('text_required')
        content=content.strip()
        if not 4<=len(content)<=1000 or any(ord(c)<32 and c not in '\n\t' for c in content):
            raise ValueError('invalid_length_or_control_characters')
        norm=' '.join(content.casefold().split())
        with self.open() as db:
            row=db.execute('SELECT id,content,origin,verified FROM notes WHERE normalized=?',(norm,)).fetchone()
            if row:return {'id':row[0],'content':row[1],'origin':row[2],'verified':bool(row[3]),'duplicate':True}
            id=str(uuid.uuid4())
            db.execute('INSERT INTO notes(id,content,normalized,origin,verified,created) VALUES(?,?,?,?,0,?)',(id,content,norm,'user_note',time.time()))
        return {'id':id,'content':content,'origin':'user_note','verified':False,'duplicate':False}
    def search(self,query:str,limit:int=5):
        if not isinstance(query,str) or len(query)>1000:raise ValueError('invalid_query')
        terms=set(words(query))
        with self.open() as db:
            rows=db.execute('SELECT id,content,origin,verified,created FROM notes ORDER BY created DESC LIMIT 500').fetchall()
        ranked=[]
        for id,content,origin,verified,created in rows:
            found=set(words(content))
            score=len(terms&found) if terms else 1
            if score:
                ranked.append((score,created,{'id':id,'content':content,'origin':origin,'verified':bool(verified)}))
        ranked.sort(key=lambda x:(-x[0],-x[1]))
        return [x[2] for x in ranked[:max(1,min(limit,20))]]
    def forget(self,id:str):
        if not isinstance(id,str) or not re.fullmatch(r'[0-9a-f-]{36}',id):raise ValueError('invalid_id')
        with self.open() as db:
            n=db.execute('DELETE FROM notes WHERE id=?',(id,)).rowcount
        return n==1

def handle_command(store:NoteStore,text:str)->str|None:
    cleaned=text.strip()
    x=cleaned.casefold()
    m=re.match(r'^(?:zapamatuj si|pamatuj si)\s*[:,-]?\s*(?:že\s+)?(.+)$',cleaned,re.IGNORECASE|re.DOTALL)
    if m:
        try:
            note=store.remember(m.group(1))
            return ('Tuhle poznámku už mám uloženou.' if note['duplicate'] else 'Uložil jsem tvoji poznámku do místní paměti. Je označená jako uživatelské tvrzení, ne jako nezávisle ověřený fakt.')
        except ValueError:
            return 'Poznámka musí obsahovat 4 až 1000 znaků bez řídicích znaků.'
    if any(x.startswith(p) for p in ('co si pamatuješ','co si pamatujes','připomeň mi','pripomen mi')):
        notes=store.search(cleaned)
        if not notes:return 'K tomu zatím nemám uloženou žádnou poznámku.'
        return 'V místní paměti mám tyto neověřené uživatelské poznámky:\n'+'\n'.join('- '+n['content'] for n in notes)
    return None
