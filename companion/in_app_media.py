"""Read-only search results for the existing Jarvis Media Bay."""
import re
import unicodedata
from urllib.parse import urlsplit
import httpx

def flat(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))

PAT = re.compile(
    r'^(?:jarvisi[,\s]+)?(?:(?:otevri|spust)\s+(?:mi\s+)?(?:prohlizec|browser)\s+a\s+)?'
    r'(?:najdi|najfi|vyhledej|ukaz|zobraz|hledej)\s+(?:mi\s+)?'
    r'(?:(?:nejake|par)\s+)?(?:obrazky|obrazek|fotky|fotografie|fotku)\s+'
    r'(?:(?:s|se|o|na|pro)\s+)?(?P<q>.+)$',re.I)

def image_query(text):
    if not isinstance(text,str) or len(text)>500:return None
    m=PAT.fullmatch(flat(text.strip()))
    if not m:return None
    q=m.group('q').strip(' .,!?')
    return q[:160] if len(q)>=2 else None

def web_url(url):
    if not isinstance(url,str) or len(url)>1800:return False
    p=urlsplit(url)
    return p.scheme in ('https','http') and bool(p.hostname) and not p.username

def image_results(query,limit=12):
    with httpx.Client(timeout=17,follow_redirects=True,headers={'User-Agent':'Mozilla/5.0'}) as c:
        r=c.get('https://duckduckgo.com/',params={'q':query})
        r.raise_for_status()
        m=re.search(r'vqd=([\d-]+)',r.text) or re.search(r'vqd="([^"]+)"',r.text)
        if not m:return []
        r=c.get('https://duckduckgo.com/i.js',
            params={'l':'us-en','o':'json','q':query,'vqd':m.group(1),'p':'1'},
            headers={'Referer':'https://duckduckgo.com/'})
        r.raise_for_status()
        data=r.json()
    out=[]
    for row in data.get('results') or []:
        url=row.get('image')
        thumb=row.get('thumbnail') or url
        if not web_url(url) or not web_url(thumb):continue
        out.append({'url':url,'thumbnail':thumb,'title':str(row.get('title') or query)[:180],
                    'source':str(row.get('source') or '')[:100]})
        if len(out)>=min(max(1,int(limit)),16):break
    return out

def link_cards(bundle):
    cards=[];seen=set()
    for row in (bundle.get('pages') or [])+(bundle.get('links') or []):
        url=row.get('url','')
        if not web_url(url) or url in seen:continue
        seen.add(url)
        cards.append({'url':url,'title':str(row.get('title') or url)[:180],
                      'snippet':str(row.get('snippet') or row.get('excerpt') or '')[:320]})
        if len(cards)>=8:break
    return cards
