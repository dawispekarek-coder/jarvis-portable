from pathlib import Path
import shutil
B=Path(r"H:\RealJarvis\V2Autonomy_20261027\BrainCore")
provider=B/"companion_image_provider.py"
s=provider.read_text(encoding="utf-8")
bak=provider.with_suffix(".before_reference_truth_20261028.py.bak")
if not bak.exists():shutil.copy2(provider,bak)
old_lali='"lali":"original friendly female raccoon with expressive warm brown eyes, small coral pink ear bow, rose pink hoodie with a tiny white heart, naturally striped fluffy raccoon tail, gray-brown cream fur"'
new_lali='"lali":"same identity as the official little female raccoon: warm gray brown cream fur, large round warm brown eyes, large cream muzzle and belly, BIG BRIGHT PINK BOW on top of her head, no shirt and no hoodie, naturally striped fluffy raccoon tail and soft paws"'
old_pooli='"pooli":"original playful male raccoon with expressive warm brown eyes, blue hoodie over a cream shirt, brown gray cream fur, striped fluffy raccoon tail"'
new_pooli='"pooli":"same identity as the official little male raccoon: warm gray brown cream fur, very large brown eyes, cream face and belly, BRIGHT BLUE BASEBALL CAP WORN BACKWARDS and BRIGHT BLUE HOODIE, fluffy striped raccoon tail, brown paws, no pink bow"'
if old_lali in s and old_pooli in s:
 s=s.replace(old_lali,new_lali).replace(old_pooli,new_pooli)
 provider.write_text(s,encoding="utf-8")
elif new_lali not in s or new_pooli not in s:
 raise SystemExit("Known prompt sources not found; refuse silent patch")
studio=B/"companion_character_studio.py"
t=studio.read_text(encoding="utf-8")
bak=studio.with_suffix(".before_candidate_rejection_20261028.py.bak")
if not bak.exists():shutil.copy2(studio,bak)
if 'def reject(' not in t:
 target=' if r["pose"] in d["characters"][who]["approved"]:raise RuntimeError("Approved pose already locked")'
 if target not in t:raise SystemExit("approve target missing")
 t=t.replace(target,' if r.get("rejected"):raise RuntimeError("Rejected candidate cannot be promoted")\n'+target)
 anchor='def story_plan(story):'
 if anchor not in t:raise SystemExit("append anchor missing")
 add='''def reject(who,candidate_id,reason):
 if who not in WHO or not isinstance(reason,str) or not 8<=len(reason)<=1000:raise ValueError("Bad rejection")
 d=load();r=d["characters"][who]["candidates"].get(candidate_id)
 if not r:raise ValueError("Candidate absent")
 if r["pose"] in d["characters"][who]["approved"]:raise RuntimeError("Already approved pose cannot be rejected this way")
 r["rejected"]=True
 r["rejection_reason"]=reason
 save(d)
 return {"verified":True,"rejected":True,"candidate_id":candidate_id,"approved":False,"originals_untouched":True}
'''
 t=t.replace(anchor,add+anchor)
 studio.write_text(t,encoding="utf-8")
registry=B/"companion_tools.py"
u=registry.read_text(encoding="utf-8")
if "character_studio_reject" not in u:
 marker=" register('character_studio_plan_story'"
 if marker not in u:raise SystemExit("registry marker missing")
 u=u.replace('approve as studio_approve, story_plan as studio_plan','approve as studio_approve, reject as studio_reject, story_plan as studio_plan')
 ins=" register('character_studio_reject','Reject visually wrong candidate; preserve immutable original and store exact critique.',{'who':{'type':'string','enum':['lali','pooli']},'candidate_id':text_schema(80),'reason':text_schema(1000)},studio_reject,write=True)\n"
 u=u.replace(marker,ins+marker)
 registry.write_text(u,encoding="utf-8")
print("REFERENCE_TRUTH_AND_REJECTION_GATES_PATCHED")
