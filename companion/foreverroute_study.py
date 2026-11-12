"""Read real ForeverRoute sources, returning verified evidence only."""
import re,unicodedata,hashlib
from project_tools import REPO,status
MODULES=('ForeverRoute_PlannerV4.lua','ForeverRoute_QuestEngine.lua','ForeverRoute_GuideLoader.lua','ForeverRoute_Navigation.lua','ForeverRoute_RoadGraph.lua','ForeverRoute_MapPins.lua','ForeverRoute_AutoQuest.lua','ForeverRoute_ControlCenter.lua','ForeverRoute_BetaCollector.lua','ForeverRoute_UIv2.lua')
def norm(s):
 return ''.join(c for c in unicodedata.normalize('NFKD',s.casefold()) if not unicodedata.combining(c))
def intent(text,recent=False):
 if not isinstance(text,str) or len(text)>1200:return False
 s=norm(text)
 project=('foreverroute' in s or 'forever route' in s)
 verbs=('nastuduj','prostuduj','precti','procti','seznam se','co vis','co znas','mas pristup','prozkoumej','zmapuj')
 return (project and any(x in s for x in verbs)) or (recent and any(x in s for x in ('nastuduj si to','prostuduj si to','precti si to')))
def read(rel):
 p=REPO/rel
 if not p.resolve().is_relative_to(REPO.resolve()) or not p.is_file() or p.is_symlink() or p.stat().st_size>2000000:raise RuntimeError('unsafe_source')
 data=p.read_bytes();text=data.decode('utf-8',errors='replace')
 return {'lines':text.splitlines(),'text':text,'hash':hashlib.sha256(data).hexdigest()}
def study(question='ForeverRoute'):
 before=status()
 readme=read('README.md')['lines'];toc=read('ForeverRoute.toc')['lines'];read('DEVELOPMENT.md')
 version=next(((i,l.split(':',1)[1].strip()) for i,l in enumerate(toc,1) if l.startswith('## Version:')),(0,'unknown'))
 loaded={x.strip().replace('\\','/') for x in toc if x.strip().endswith('.lua')}
 info=[]
 for name in MODULES:
  if name not in loaded:continue
  f=read(name)
  symbols=re.findall(r'^\s*(?:local\s+)?function\s+([A-Za-z_][\w.:]*)',f['text'],re.M)
  info.append((name,len(f['lines']),symbols[:2],f['hash']))
 if len(info)<7:raise RuntimeError('modules_not_found')
 wanted=('Current public version','levels 1-60','13 level bands','step-by-step quest guidance','native Blizzard waypoint','Current development priorities')
 facts=[(i,l.strip()) for i,l in enumerate(readme,1) if any(w.casefold() in l.casefold() for w in wanted)][:6]
 if not facts:raise RuntimeError('readme_no_evidence')
 after=status()
 if any(before[k]!=after[k] for k in ('commit','branch','changed_count')):raise RuntimeError('source_changed')
 return {'commit':before['commit'],'branch':before['branch'],'version':version,'facts':facts,'modules':info,'source_count':3+len(info),'verified':True,'read_only':True}
def format_study(s):
 line,version=s['version']
 output=['Skutečně jsem otevřel a prostudoval lokální zdrojový kód ForeverRoute (jen čtení).',
 'Git: '+s['branch']+' / '+s['commit'],
 'Verze dle TOC: '+version+' [ForeverRoute.toc:'+str(line)+']',
 'Konkrétní fakta z README:']
 output+=['- '+v[:160]+' [README.md:'+str(i)+']' for i,v in s['facts'][:4]]
 output.append('Otevřené Lua moduly z herního načítacího seznamu:')
 output+=['- '+name+' ('+str(n)+' řádků'+('; funkce '+', '.join(symbols) if symbols else '')+')' for name,n,symbols,_ in s['modules']]
 output.append('Načetl jsem '+str(s['source_count'])+' souborů. Jde o ověřený přístup ke kódu, ne o ověřený úspěch všech funkcí ve hře. Nic jsem nepřepsal.')
 return '\n'.join(output)[:3700]
