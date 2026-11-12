from pathlib import Path
p=Path(r'H:\RealJarvis\V2Autonomy_20261027\BrainCore\companion_agent.py')
s=p.read_text(encoding='utf8')
backup=p.with_suffix('.py.before_story_route_20261028.bak')
if not backup.exists():backup.write_bytes(p.read_bytes())
if "required={'lali_pooli_autonomous_director'}" not in s:
 marker=" groups=[]"
 assert s.count(marker)==1
 s=s.replace(marker," if action and 'lali' in n and 'pooli' in n and any(k in n for k in ('video','reel','animac','scenk')) and any(k in n for k in ('vytvor','udel','vyrenderuj','priprav')):required={'lali_pooli_autonomous_director'}\n"+marker,1)
if "return choose('lali_pooli_autonomous_director'" not in s:
 marker=" if ('audit' in n or 'kvalit' in n or 'hodnot' in n) and 'lali' in n and 'pooli' in n:"
 assert s.count(marker)==1
 s=s.replace(marker," if 'lali' in n and 'pooli' in n and any(k in n for k in ('video','reel','animac','scenk')) and any(k in n for k in ('vytvor','udel','vyrenderuj','priprav')):return choose('lali_pooli_autonomous_director',{'goal':goal})\n"+marker,1)
if "if name=='lali_pooli_autonomous_director'" not in s:
 marker=" if name=='godot_2d_production_quality_audit':return"
 assert s.count(marker)==1
 s=s.replace(marker," if name=='lali_pooli_autonomous_director':return 'Vytvoril jsem petizaberovy plan: '+str(v.get('title'))+'. Jeho validace: '+str(v.get('plan_valid'))+'. Video: '+str(v.get('draft_mp4','nevyrobeno'))+'. Kvalita zatim neschvalena, nikdy nepublikovat. Report: '+str(v.get('manifest'))\n"+marker,1)
p.write_text(s,encoding='utf8')
print('PATCHED_ROUTING',s.count('lali_pooli_autonomous_director'))
