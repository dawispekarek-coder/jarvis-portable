"""RealJarvis V2: bounded, privacy-conscious learning from verified tool outcomes.
Not LLM weight training. External text never becomes authority or executable code.
"""
from pathlib import Path
from urllib.parse import urlparse
from contextlib import contextmanager
import sqlite3,time,re,json,threading
DB=Path(__file__).resolve().parent/'experience.sqlite'
_LOCK=threading.RLock()
_PRIVATE=re.compile(r'(?i)(password|heslo|token|api[_-]?key|secret|bearer)')

def host_of(url):
    try:
        p=urlparse(url)
        if p.scheme!='https' or not p.hostname:return ''
        host=p.hostname.lower()
        if host=='localhost' or host.endswith(('.local','.internal')):return ''
        return host[:120]
    except (ValueError,TypeError):return ''

@contextmanager
def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    with _LOCK:
        cx=sqlite3.connect(DB,timeout=10)
        try:
            cx.execute('CREATE TABLE IF NOT EXISTS outcomes ('
             'id INTEGER PRIMARY KEY, domain TEXT NOT NULL, method TEXT NOT NULL, '
             'outcome TEXT NOT NULL, evidence INTEGER NOT NULL, timestamp REAL NOT NULL)')
            cx.execute('CREATE INDEX IF NOT EXISTS idx_outcome_host ON outcomes(domain,timestamp)')
            yield cx
            cx.commit()
        finally:cx.close()

def observe_url(url,method,success,verified):
    """Only real tool observations; store hostname not URL, prompt, or content."""
    domain=host_of(url)
    if not domain or method not in ('read_public_page',):return False
    if type(success) is not bool or type(verified) is not bool:return False
    if not verified:return False
    with connect() as db:
        db.execute('INSERT INTO outcomes(domain,method,outcome,evidence,timestamp) VALUES (?,?,?,?,?)',
            (domain,method,'success' if success else 'failure',2 if success else 1,time.time()))
        db.execute('DELETE FROM outcomes WHERE timestamp<?',(time.time()-60*86400,))
        db.execute('DELETE FROM outcomes WHERE id NOT IN (SELECT id FROM outcomes ORDER BY timestamp DESC LIMIT 4000)')
    return True
def statistics(domain):
    if not domain or not isinstance(domain,str):return {'success':0,'failure':0,'sample':0}
    with connect() as db:
        rows=db.execute('SELECT outcome,count(*) FROM outcomes WHERE domain=? GROUP BY outcome',(domain,)).fetchall()
    a=dict(rows)
    return {'success':int(a.get('success',0)),'failure':int(a.get('failure',0)),
            'sample':sum(n for _,n in rows)}

def order_sources(links):
    """After >=3 observations, gently prioritize readable domains; preserve diversity.
    Never block new domains and never declare a source factually trustworthy.
    """
    if not isinstance(links,list):return []
    candidates=[x for x in links[:10] if isinstance(x,dict) and host_of(x.get('url',''))]
    def score(hit):
        stats=statistics(host_of(hit.get('url','')))
        if stats['sample']<3:return 0
        return max(-2,min(2,stats['success']-stats['failure']))
    # Stable sort keeps original search relevance for sources with no history.
    result=sorted(candidates,key=score,reverse=True)
    # Preserve a new domain in first five, to avoid a self-reinforcing bubble.
    if len(result)>1 and not any(statistics(host_of(x['url']))['sample']==0 for x in result[:5]):
        new=next((i for i,x in enumerate(result[5:],5) if statistics(host_of(x['url']))['sample']==0),None)
        if new is not None:result.insert(4,result.pop(new))
    return result

def summary():
    with connect() as db:
        a=dict(db.execute('SELECT outcome,count(*) FROM outcomes GROUP BY outcome').fetchall())
        d=db.execute('SELECT count(DISTINCT domain) FROM outcomes').fetchone()[0]
        n=db.execute('SELECT count(*) FROM outcomes').fetchone()[0]
    return {'learning_active':True,'model_weights_retrained':False,
            'verified_observations':n,'successful_reads':a.get('success',0),
            'failed_reads':a.get('failure',0),'observed_domains':d,
            'adaptation':'domain_readability_ranking_after_3_observations',
            'storage':'local_hostname_only','user_feedback_as_proof':False}
def explain():
    stats=summary()
    n=stats['verified_observations']
    if not n:
        return 'Zatím nemám ověřené zkušenosti z práce s webovými zdroji. Nezačal jsem přeučovat jazykový model.'
    return ('Učím se z reálných výsledků nástrojů: '+str(n)+' ověřených pokusů o čtení stránek, '
      +str(stats['successful_reads'])+' úspěšných, '+str(stats['failed_reads'])+
      ' neúspěšných, z '+str(stats['observed_domains'])+' domén. '
      'Po několika pozorováních upravuji pořadí technicky dostupných zdrojů, nikoliv pravidla bezpečnosti nebo váhy modelu. '
      'Zkušenosti ukládám lokálně bez celých URL, dotazů či hesel.')

def is_learning_question(text):
    if not isinstance(text,str):return False
    from behavior_router import normalize
    s=normalize(text.strip())
    return any(s.startswith(x) for x in ('co ses naucil','jak se ucis','jak jsi se naucil',
      'ukaz sve zkusenosti','ukaz co ses naucil','ukaž co ses naucil')) and len(s)<100
