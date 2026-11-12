from pathlib import Path
from companion_settings import ROOT,STATE
from companion_tools import build_registry
from companion_store import Store
from companion_agent import known_call,goal_contract
import knowledge
term="LALI_POOLI_REUSABLE_MASTER_20261028"
print("KNOWLEDGE_EXISTS",(ROOT/"KnowledgeInbox"/(term+".md")).is_file())
result=knowledge.search("LALI POOLI master reusable character",limit=8)
print("KNOWLEDGE_MATCHES",len(result))
r=build_registry(Store(STATE),{"id":"live-catalog","conversation_id":"live-catalog","goal":"status"})
print("MASTER_STATUS_TOOL",r.execute("character_studio_status",{})["ok"])
print("LIVE_ROUTE",known_call("Stav knihovny Lali a Pooli",set(r.entries)))
print("STORY_REQUIRED",goal_contract("Vytvor video Lali a Pooli jak se vraci domu")["required"])
