"""Open a normal browser search after explicit Czech 'najdi' intent.
The actual evidence gathering is separately verified by research_agent.
"""
import re,subprocess
from pathlib import Path
from urllib.parse import quote

EDGE=Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
SENSITIVE=re.compile(r'(?i)(api[_ -]?key|password|heslo|bearer|secret|token|sk-[a-z0-9]{8,})')

def open_search_window(query):
    if not isinstance(query,str) or not 3<=len(query)<=200 or SENSITIVE.search(query):
        return {'opened':False,'reason':'invalid_or_private_query'}
    if not EDGE.is_file():
        return {'opened':False,'reason':'browser_missing'}
    url='https://duckduckgo.com/?q='+quote(query,safe='')
    try:
        proc=subprocess.Popen([str(EDGE),'--inprivate','--new-window',url],
           stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
           creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        return {'opened':proc.pid>0,'url':url,'pid':proc.pid,'note':'browser_window_launched_not_page_verified'}
    except OSError:
        return {'opened':False,'reason':'browser_launch_failed'}