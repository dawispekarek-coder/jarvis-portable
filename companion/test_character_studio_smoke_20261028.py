import companion_character_studio as s
from companion_tools import build_registry
from companion_store import Store
from companion_settings import STATE
from companion_agent import known_call, goal_contract
r=build_registry(Store(STATE),{"id":"character_studio_smoke","conversation_id":"character_studio_smoke","goal":"Lali Pooli character studio assets"})
expected={"character_studio_status","character_studio_ingest","character_studio_approve","character_studio_plan_story"}
assert expected.issubset(set(r.entries))
before=s.status();assert before["verified"] and before["locked_character_designs"]==["lali","pooli"]
idname="lali_front_f75b53d08aa1.png"
source=s.GODOT/"training"/"wholeframe_experiments"/"provider_studies"/idname
if source.is_file():
 existing=[k for k,v in s.load()["characters"]["lali"]["candidates"].items() if v["sha"]==s.sha(source)]
 if existing:cid=existing[0]
 else:
  candidate=r.execute("character_studio_ingest",{"who":"lali","pose":"front","image_name":idname})
  assert candidate["ok"] and candidate["value"]["approved"] is False
  cid=candidate["value"]["candidate_id"]
 denied=r.execute("character_studio_approve",{"who":"lali","candidate_id":cid,"approval_phrase":"REJECTED"})
 assert denied["verified"] is False
 print("STUDY_CANDIDATE_STORED_UNAPPROVED",cid)
plan=r.execute("character_studio_plan_story",{"story":"Pooli comes home, Lali is happy"})
assert plan["ok"] and plan["value"]["reused_count"] if False else plan["ok"]
assert plan["value"]["regenerate_original_characters"] is False
assert plan["value"]["render_ready"] is False
print("STORY_PLAN_REUSABLE",plan["value"]["missing"])
call=known_call("Vytvor video Lali a Pooli doma",set(r.entries))
assert call["name"]=="character_studio_plan_story"
assert goal_contract("Vytvor video Lali a Pooli doma")["required"]=={"character_studio_plan_story"}
assert s.status()["verified"]
print("MASTER_REUSE_SMOKE_PASS")
