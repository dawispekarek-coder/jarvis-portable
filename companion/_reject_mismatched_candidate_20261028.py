from pathlib import Path
from companion_character_studio import reject,load,status,ROOT
from companion_store import Store
from companion_settings import STATE,ROOT as JROOT
cid="lali_front_6b39fd5c04c1"
reason="Rejected as a master: SDXL prompt asked for a pink hoodie, but canonical Lali has cream fur and only a bright pink head bow, with no hoodie. Text-only SDXL does not use the original reference image."
record=load()["characters"]["lali"]["candidates"].get(cid)
if record is None:raise SystemExit("Candidate missing")
if not record.get("rejected"):print("REJECT_RESULT",reject("lali",cid,reason))
d=load()
assert d["characters"]["lali"]["candidates"][cid]["rejected"]
try:
 from companion_character_studio import approve
 approve("lali",cid,"SCHVALUJI MASTER "+cid)
 raise SystemExit("FAILED: rejected candidate was approved")
except RuntimeError as exc:
 print("REJECTED_CANNOT_BE_PROMOTED",str(exc))
assert not d["characters"]["lali"]["approved"]
truth="""CANONICAL CHARACTER LOCK (verified visually 2026-10-28)
Lali: furry female little raccoon, brown/gray fur with cream muzzle/belly, big brown eyes, big PINK HEAD BOW. NO pink hoodie, NO other clothing.
Pooli: furry male little raccoon, cream muzzle/belly, expressive brown eyes, BLUE HOODIE, BLUE BASEBALL CAP WORN BACKWARDS, striped tail.
Old generated character concept with pink-hoodie Lali is WRONG and was rejected. It must never become master art.
Free OVH SDXL API is TEXT ONLY: cannot image-reference lock; visually compare every study.
"""
note=JROOT/"KnowledgeInbox"/"LALI_POOLI_EXACT_IDENTITY_20261028.md"
note.write_text(truth,encoding="utf-8")
with (ROOT/"MASTER_RULES.txt").open("a",encoding="utf-8") as f:f.write("\n"+truth)
Store(STATE).remember("skill:lali_pooli_exact_visual_identity",truth,"verified_reference_comparison")
page=ROOT/"CHARACTER_BIBLE.html"
html=page.read_text(encoding="utf-8")
html=html.replace(cid+" - UNAPPROVED",cid+" - REJECTED / WRONG CLOTHING")
page.write_text(html,encoding="utf-8")
print("IDENTITY_LESSON_AND_REJECT_QA",status()["verified"])
