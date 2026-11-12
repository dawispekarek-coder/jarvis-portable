"""Bounded second-source verification; never treats a second URL as proof of truth."""
from __future__ import annotations
from urllib.parse import urlparse
from public_search import SearchUnavailable
from page_reader import PageUnavailable
from research_evidence import assess,MAX_OPEN,MAX_ATTEMPTS
MAX_FOLLOWUP_READS=3
MAX_FOLLOWUP_ACCEPTED=1
def _host(hit):
    return (urlparse(hit.get('url','')).hostname or '').lower()
def needs_followup(bundle):
    audit=bundle.get('audit') or assess(bundle)
    return bool(bundle.get('pages')) and bool(audit.get('sources_limited') or audit.get('potential_numeric_mismatches'))
def enrich(bundle, searcher, reader):
    """Never send page excerpts to search; only the original user's public query."""
    bundle['followup']={'attempted':False,'read':0,'reason':'not_required'}
    if not needs_followup(bundle):
        return bundle
    query=bundle.get('query','')
    if not isinstance(query,str) or not 3<=len(query.strip())<=160:
        bundle['followup']['reason']='invalid_original_query'
        return bundle
    bundle['followup']={'attempted':True,'read':0,'reason':'no_additional_readable_source'}
    original={p.get('url') for p in bundle.get('pages',[])}
    used_domains={_host(p) for p in bundle.get('pages',[])}
    search_query=(query+' official documentation')[:200]
    try:
        results=searcher(search_query).get('results',[])
    except (SearchUnavailable,OSError,ValueError,TypeError,KeyError):
        bundle['followup']['reason']='search_unavailable'
        return bundle
    tries=0
    for hit in results[:MAX_ATTEMPTS]:
        url=hit.get('url')
        host=_host(hit)
        if not isinstance(url,str) or url in original or not host or host in used_domains:
            continue
        tries+=1
        try:
            page=reader(hit)
            if page.get('url')!=url or len(page.get('excerpt','').strip())<80:
                raise PageUnavailable('invalid_source_content')
        except (PageUnavailable,OSError,ValueError,KeyError,TypeError):
            if tries>=MAX_FOLLOWUP_READS:break
            continue
        kept={'title':page.get('title') or hit.get('title',''),
              'url':url,'excerpt':page['excerpt'][:1250],
              'read_only':True,'verification_followup':True}
        bundle.setdefault('pages',[]).append(kept)
        bundle['followup']['read']=1
        bundle['followup']['reason']='additional_source_read'
        break
    bundle['audit']=assess(bundle)
    bundle['evidence_level']=2 if bundle.get('pages') else (1 if bundle.get('links') else 0)
    return bundle
