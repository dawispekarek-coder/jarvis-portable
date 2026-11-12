from pathlib import Path
p=Path(r'H:\RealJarvis\V2Autonomy_20261027\BrainCore\companion_video_director.py')
s=p.read_text(encoding='utf8')
backup=p.with_suffix('.py.before_reference20_render_20261028.bak')
if not backup.exists():backup.write_bytes(p.read_bytes())
if 'def learned_techniques()' not in s:
 anchor='def make_plan(goal):'
 assert anchor in s
 helper="""def learned_techniques():
    ref=R/'training'/'learning20'/'lessons_for_director.txt'
    if not ref.is_file():return ''
    lines=ref.read_text(encoding='utf8').splitlines()
    if len(lines)<20:return ''
    return '\\n'+'VERIFIED SAMPLED REFERENCE LESSONS (TECHNIQUES ONLY, NEVER COPY ART/SHOTS):\\n'+ '\\n'.join(x[:220] for x in lines[:20])+'\\n'
"""
 s=s.replace(anchor,helper+anchor,1)
 s=s.replace("'content':SYS+goal}","'content':SYS+goal+learned_techniques()}",1)
if "from companion_homecoming_render import render_homecoming" not in s:
 marker=" plan=make_plan(goal); faults=audit_plan(plan,goal);gate=quality_gate()"
 assert marker in s
 s=s.replace(marker,marker+"\n draft=None\n if not faults and 'prace' in norm(goal) and 'dom' in norm(goal) and (R/'training'/'learning20'/'lessons_for_director.txt').is_file():\n  from companion_homecoming_render import render_homecoming\n  try:draft=render_homecoming()\n  except Exception as exc:draft={'stage':'RENDER_FAILED','error':type(exc).__name__+': '+str(exc)[:240]}",1)
 s=s.replace("'instagram_posted':False,'stage':'PLAN_NEEDS_REVISION' if faults else 'ASSETS_BLOCK_PRODUCTION'}",
  "'instagram_posted':False,'draft_render':draft,'stage':'PLAN_NEEDS_REVISION' if faults else 'DRAFT_NOT_APPROVED' if draft and draft.get('preview_file') else 'ASSETS_BLOCK_PRODUCTION'}",1)
 s=s.replace("'finished_video':False,'published':False,'manifest':str(report),'blockers':gate['blockers']}",
  "'finished_video':False,'published':False,'draft_mp4':draft.get('preview_file') if draft else None,'render_result':draft,'manifest':str(report),'blockers':gate['blockers']}",1)
p.write_text(s,encoding='utf8')
print('DIRECTOR_UPDATED',len(s))
