from companion_tools import build_registry
from companion_store import Store
from companion_settings import STATE
import json
r=build_registry(Store(STATE),{"id":"vision_qa_test","conversation_id":"vision_qa_test","goal":"Porovnej original Lali s kresbou a najdi chyby"})
res=r.execute("character_studio_visual_review",{"who":"lali","candidate_id":"lali_front_294b8c80276a"})
print("REVIEW_VERIFIED",res["ok"])
print("REVIEW_RESULT",json.dumps(res.get("value",res.get("error")),ensure_ascii=True))
if not res["ok"]:raise SystemExit(1)
