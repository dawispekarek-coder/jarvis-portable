"""RealJarvis searches still use actual web tools, but learn source readability.
The model never decides which experience is verified: the actual page reader does.
"""
from public_search import search as public_search
from page_reader import read_result as public_read,PageUnavailable
from research_agent import research as original_research
import experience_learning as memory

def research(query,searcher=public_search,reader=public_read):
    def adaptive_search(text):
        result=searcher(text)
        result=dict(result)
        result['results']=memory.order_sources(result.get('results',[]))
        return result
    def observable_reader(hit):
        url=hit.get('url','')
        try:
            page=reader(hit)
            if page.get('url')==url and len(page.get('excerpt','').strip())>=80:
                memory.observe_url(url,'read_public_page',True,True)
            return page
        except (PageUnavailable,OSError,ValueError,KeyError,TypeError):
            # Only actual page reading errors count as negative observations.
            memory.observe_url(url,'read_public_page',False,True)
            raise
    return original_research(query,searcher=adaptive_search,reader=observable_reader)