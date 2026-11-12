from companion_character_studio import load,ingest,reject,status
from companion_settings import ROOT as JROOT,STATE
from companion_store import Store
from pathlib import Path
name="lali_front_e322c2a0ffb5.png"
d=load()
existing=[k for k,v in d["characters"]["lali"]["candidates"].items() if v["file"].endswith(name)]
if existing:cid=existing[0]
else:cid=ingest("lali","front",name)["candidate_id"]
reason=("Visual QA FAIL against canonical Lali: model drew a SECOND large pink bow at her NECK/chest, "
        "instead of the single official head bow; face proportions, fur design, pose and outfit details "
        "do not match the official reference. Free text-only SDXL cannot lock visual identity.")
r=reject("lali",cid,reason)
print("SECOND_CANDIDATE_REJECTED",r)
p=JROOT/"KnowledgeInbox"/"LALI_POOLI_CHARACTER_FAILURES_20261028.md"
text=p.read_text(encoding="utf-8") if p.exists() else ""
text+="\nRejected "+cid+": "+reason+"\n"
p.write_text(text,encoding="utf-8")
Store(STATE).remember("lesson:lali_second_bow_failure",reason,"visual_qa_rejected")
assert status()["verified"]
print("MASTER_LIBRARY_UNCHANGED",status()["approved_pose_sets"])
