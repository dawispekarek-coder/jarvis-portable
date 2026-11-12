from pathlib import Path
import shutil
B=Path(r"H:\RealJarvis\V2Autonomy_20261027\BrainCore")
p=B/"companion_tools.py"
s=p.read_text(encoding="utf-8")
anchor=" registry.desktop=desktop"
if "character_studio_plan_story" not in s:
 if anchor not in s:raise SystemExit("registry anchor not found")
 backup=p.with_suffix(".before_character_studio_20261028.py.bak")
 if not backup.exists():shutil.copy2(p,backup)
 add=""" from companion_character_studio import init as studio_init, status as studio_status, ingest as studio_ingest, approve as studio_approve, story_plan as studio_plan
 register('character_studio_initialize','Build persistent immutable original Lali/Pooli design and expression library.',{},studio_init,write=True)
 register('character_studio_status','Verify saved Lali/Pooli master designs, expressions, pose packs and SHA hashes.',{},studio_status)
 register('character_studio_ingest','Store generated experimental pose only as unapproved candidate, never change original.',{'who':{'type':'string','enum':['lali','pooli']},'pose':text_schema(30),'image_name':text_schema(100)},studio_ingest,write=True)
 register('character_studio_approve','Only promote one inspected drawing with explicit exact owner approval phrase.',{'who':{'type':'string','enum':['lali','pooli']},'candidate_id':text_schema(80),'approval_phrase':text_schema(120)},studio_approve,write=True,approval=True)
 register('character_studio_plan_story','Reuse locked approved Lali/Pooli character assets and list missing motion without generating replacement characters.',{'story':text_schema(1600)},studio_plan,required=['story'])
"""
 p.write_text(s.replace(anchor,add+anchor),encoding="utf-8")
a=B/"companion_agent.py"
s=a.read_text(encoding="utf-8")
if "character_studio_plan_story" not in s:
 backup=a.with_suffix(".before_character_studio_20261028.py.bak")
 if not backup.exists():shutil.copy2(a,backup)
 old="required={'lali_pooli_autonomous_director'}"
 if old not in s:raise SystemExit("goal route anchor missing")
 s=s.replace(old,"required={'character_studio_plan_story'}")
 old="return choose('lali_pooli_autonomous_director',{'goal':goal})"
 if old not in s:raise SystemExit("known route anchor missing")
 s=s.replace(old,"return choose('character_studio_plan_story',{'story':goal})")
 pos=" def choose(name,args):return"
 if pos not in s:raise SystemExit("known_call insert anchor missing")
 # Do not intercept study generator prompts; status only when asked for library.
 block=""" if ('knihovn' in n or 'master postav' in n) and ('lali' in n or 'pooli' in n):
  return choose('character_studio_status',{})
"""
 loc=" if 'lali' in n and 'pooli' in n and any(k in n for k in ('video','reel','animac','scenk'))"
 if loc not in s:raise SystemExit("known_call location missing")
 s=s.replace(loc,block+loc,1)
 s=s.replace("SYSTEM='''","SYSTEM='''REUSE POLICY: Lali and Pooli have IMMUTABLE master designs in character_studio. Always reuse APPROVED poses for Reels; do not redraw characters from scratch every video. Missing art stays missing; never reuse rejected sliced sprites. No publishing without approval.\\n",1)
 a.write_text(s,encoding="utf-8")
print("PATCH_STUDIO_TOOLS_AND_ROUTES_DONE")
