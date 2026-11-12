"""Free public web search via DuckDuckGo Lite, read-only, no API key.
Only source title/URL is trusted as retrieved metadata; no factual synthesis.
"""
from __future__ import annotations
import html,re,unicodedata
from html.parser import HTMLParser
from urllib.parse import urlparse,parse_qs,unquote
import httpx

ENDPOINT='https://lite.duckduckgo.com/lite/'
MAX_RESULTS=6
STOP={'jak','jaky','jaké','jake','kde','kdo','jsou','pro','the','and','what','about','info','informace','najdi','vyhledej','dnes','webu','internetu'}

class SearchUnavailable(RuntimeError):pass

class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[]
        self.href=None
        self.content=[]
    def handle_starttag(self,tag,attrs):
        if tag!='a':return
        attr=dict(attrs)
        href=attr.get('href','')
        if isinstance(href,str) and href:
            self.href=href
            self.content=[]
    def handle_data(self,data):
        if self.href is not None:self.content.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.href is not None:
            self.links.append((self.href,' '.join(''.join(self.content).split())))
            self.href=None
            self.content=[]

def normalize_words(text):
    value=unicodedata.normalize('NFKD',text.casefold())
    value=''.join(c for c in value if not unicodedata.combining(c))
    return set(w for w in re.findall(r'[a-z0-9]{4,}',value) if w not in STOP)

def destination(href):
    if href.startswith('//'):href='https:'+href
    p=urlparse(href)
    if p.scheme not in ('http','https'):return None
    host=(p.hostname or '').lower()
    if host in ('duckduckgo.com','www.duckduckgo.com') and p.path.startswith('/l/'):
        target=parse_qs(p.query).get('uddg',[''])[0]
        href=unquote(target) if '%25' in target else target
        p=urlparse(href);host=(p.hostname or '').lower()
    if p.scheme!='https' or not host or host in ('localhost','127.0.0.1'):
        return None
    if host.endswith('.local') or host.endswith('.internal') or host.startswith(('10.','192.168.','172.16.')):
        return None
    if host in ('duckduckgo.com','www.duckduckgo.com'):return None
    return href.split('#',1)[0]

def parse_results(page,query):
    if not isinstance(page,str) or len(page)>500_000:raise SearchUnavailable('invalid_html')
    if any(x in page.casefold() for x in ('anomaly-modal','please complete the captcha','security check - substation')):
        raise SearchUnavailable('anti_bot')
    parser=Links()
    parser.feed(page)
    terms=normalize_words(query)
    if not terms:raise ValueError('empty_search_terms')
    results=[];seen=set()
    for href,title in parser.links:
        target=destination(html.unescape(href))
        if not target or not title or len(title)<5:continue
        if target in seen:continue
        relevant=terms & normalize_words(title+' '+urlparse(target).path+' '+urlparse(target).netloc)
        if not relevant:continue
        seen.add(target)
        results.append({'title':title[:160],'url':target[:500],'matched_terms':len(relevant)})
        if len(results)>=MAX_RESULTS:break
    return results

def extract_request(text):
    if not isinstance(text,str):return None
    value=text.strip()
    prefixes=('/web ','/search ','web:','vyhledej na internetu ','najdi na internetu ',
              'vyhledej na webu ','najdi na webu ','najdi informace o ')
    for prefix in prefixes:
        if value.casefold().startswith(prefix):
            return value[len(prefix):].strip()
    return None

def search(query:str):
    if not isinstance(query,str) or not 4<=len(query.strip())<=200:
        raise ValueError('invalid_query')
    with httpx.Client(timeout=14,follow_redirects=False,
       headers={'User-Agent':'Mozilla/5.0 (compatible; JarvisReadOnly/2.0)',
                'Accept':'text/html'}) as client:
        try:
            rsp=client.get(ENDPOINT,params={'q':query})
            if rsp.status_code!=200 or 'html' not in rsp.headers.get('content-type','').lower():
                raise SearchUnavailable('http_unavailable')
            results=parse_results(rsp.text,query)
        except httpx.HTTPError as exc:
            raise SearchUnavailable('network_unavailable') from exc
    return {'query':query,'provider':'DuckDuckGo Lite','results':results,'read_only':True}

def format_results(data):
    if not data['results']:
        return ('Vyhledávač odpověděl, ale nenašel jsem dostatečně relevantní odkazy '
                'pro dotaz: '+data['query']+'. Nebudu si je vymýšlet.')
    lines=['Výsledky skutečného webového vyhledávání (DuckDuckGo Lite):']
    for i,hit in enumerate(data['results'],1):
        lines.append(f"{i}. {hit['title']}\n{hit['url']}")
    lines.append('Jsou to nalezené odkazy, nikoli ověřený obsah článků nebo potvrzení aktuálnosti.')
    return '\n'.join(lines)
