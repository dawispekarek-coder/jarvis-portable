"""Real network verification with intentionally single-source first-pass fixture."""
import json
from public_search import search
from page_reader import read_result
from research_agent import research
q='LangGraph Python documentation'
calls=[]
def finder(query):
 calls.append(query)
 data=search(query)
 if len(calls)==1:data['results']=data['results'][:1]
 return data
x=research(q,searcher=finder,reader=read_result,
           summarizer=lambda b:'Kontrolní průchod načetl podklady s jejich URL.')
print(json.dumps({'requests':calls,'pages':len(x['pages']),
  'hosts':[p['url'].split('/')[2] for p in x['pages']],
  'second_source_read':x['followup']['read'],'reason':x['followup']['reason'],
  'audit':x['audit'],'report_tail':x['reply'][-500:]},ensure_ascii=True),flush=True)