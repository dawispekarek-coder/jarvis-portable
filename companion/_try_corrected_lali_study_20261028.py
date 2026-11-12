import json
from companion_tools import build_registry
from companion_store import Store
from companion_settings import STATE
r=build_registry(Store(STATE),{"id":"corrected_art_study","conversation_id":"corrected_art_study","goal":"Nakresli zkusebni Lali podle presne puvodni predlohy a nic neschvaluj"})
result=r.execute("image_study_draw",{"character":"lali","pose":"front"})
print("DRAW_TOOL_OK",result["ok"])
print("DRAW_RESULT",json.dumps(result.get("value",result.get("error")),ensure_ascii=True))
if not result["ok"]:raise SystemExit(1)
