"""Isolated DDGS adapter; retrieved links are never proof of originality."""
import json,subprocess,ipaddress,time
from pathlib import Path
from urllib.parse import urlsplit
PYTHON=Path(r'H:\RealJarvis\OptionalPlugins\JarvisResearch\.venv\Scripts\python.exe')

def validate_query(query):
 if not isinstance(query,str) or not 4<=len(query.strip())<=300:raise ValueError('invalid_query')
 return query.strip()

def normalize_results(query,raw,backend):
 items=[];seen=set()
 for row in raw[:20]:
  url=str(row.get('href') or row.get('url') or '')
  try:
   p=urlsplit(url);host=p.hostname or ''
   if p.scheme!='https' or not host or p.username or p.password:continue
   if host=='localhost' or host.endswith(('.local','.internal')):continue
   try:
    if not ipaddress.ip_address(host).is_global:continue
   except ValueError:pass
  except ValueError:continue
  if url in seen:continue
  seen.add(url);items.append({'title':str(row.get('title',''))[:200],'url':url[:1500],'snippet':str(row.get('body',''))[:700]})
  if len(items)>=6:break
 return {'query':query,'provider':'DDGS/'+backend,'retrieved_at':time.time(),'results':items,'status':'RESULTS' if items else 'NO_RESULTS','verified':True,'pages_read':False,'originality_verified':False,'scope':'Search completed; snippets only. No results does not prove uniqueness; use web_read to inspect sources.'}

def search_secondary(query,backend='bing'):
 query=validate_query(query)
 if backend not in ('bing','brave','google'):raise ValueError('invalid_backend')
 if not PYTHON.is_file():raise RuntimeError('secondary_search_not_installed')
 code="import json,sys;from ddgs import DDGS;p=json.load(sys.stdin);print(json.dumps(DDGS(timeout=12).text(p['query'],max_results=6,backend=p['backend']),ensure_ascii=True))"
 result=subprocess.run([str(PYTHON),'-c',code],input=json.dumps({'query':query,'backend':backend}),capture_output=True,text=True,encoding='utf-8',timeout=25,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if result.returncode:raise RuntimeError('secondary_search_failed: '+result.stderr[-300:])
 raw=json.loads(result.stdout)
 if not isinstance(raw,list):raise ValueError('invalid_search_response')
 return normalize_results(query,raw,backend)

def format_search(value):
 items=value.get('results',[])
 if not items:return 'Druhý vyhledávač nenašel výsledky. To neprokazuje, že podobný koncept neexistuje.'
 return 'Druhý vyhledávač našel '+str(len(items))+' odkazů:\n'+'\n'.join('- '+r['title'] for r in items)+'\nZatím jsou to názvy a úryvky; podobnost ani původnost nejsou ověřené. Podklady je nutné přečíst.'

