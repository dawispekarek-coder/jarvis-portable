"""AI-assisted quality review. Advisory ONLY: model response never approves a master."""
from pathlib import Path
from PIL import Image
import io,base64,json,urllib.request,re
from companion_character_studio import ROOT, load, sha
def review(who,candidate_id):
 if who not in ("lali","pooli") or not re.fullmatch(r"(lali|pooli)_[a-z_]+_[0-9a-f]{12}",candidate_id):
  raise ValueError("invalid candidate")
 d=load();entry=d["characters"][who]["candidates"].get(candidate_id)
 if not entry:raise ValueError("Candidate not in canonical library")
 source=ROOT/"refs"/who/"fullbody.png"
 target=ROOT/entry["file"]
 if sha(target)!=entry["sha"]:raise RuntimeError("Candidate hash mismatch")
 def encode(path):
  with Image.open(path) as img:
   img=img.convert("RGBA")
   bg=Image.new("RGBA",img.size,(255,255,255,255))
   bg.alpha_composite(img)
   view=bg.convert("RGB");view.thumbnail((640,640))
   out=io.BytesIO();view.save(out,format="JPEG",quality=76)
  return base64.b64encode(out.getvalue()).decode("ascii")
 prompt=("Compare two ORIGINAL independently-created cartoon characters. Do not invent any movie, franchise or source attribution. IMAGE 1 is the authoritative original of "+who+
 ". IMAGE 2 is a proposed NEW frame. Assess whether they are the SAME specific cartoon character. "
 "List concrete visual deviations, full-body cropping and extra limbs, clothing/ears/tail problems. "
 "LALI must have ONE PINK BOW on head, NO hoodie and NO NECK bow. POOLI must have BLUE CAP worn backwards AND BLUE HOODIE. "
 "DO NOT merely say both pictures depict raccoons. Give Czech response max 110 words, "
 "and verdict MATCH/DIFFERENT/UNCERTAIN. A match cannot approve an image.")
 payload={"model":"qwen3.5:4b-q4_K_M","messages":[{"role":"user","content":prompt,
    "images":[encode(source),encode(target)]}],"stream":False,"think":False,
    "options":{"temperature":0.1,"num_ctx":4096,"num_predict":260}}
 req=urllib.request.Request("http://127.0.0.1:11434/api/chat",
   data=json.dumps(payload).encode("utf-8"),headers={"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=140) as r:
  v=json.load(r)
 text=v.get("message",{}).get("content","").strip()
 if not text:raise RuntimeError("Vision model gave no answer")
 report={"character":who,"candidate":candidate_id,"reference_sha256":sha(source),
     "candidate_sha256":entry["sha"],"vision_model":"qwen3.5:4b-q4_K_M",
     "observation":text[:2100],"visual_approval":False,
     "model_observation_only":True,"manual_approval_required":True,
     "rejected_already":entry.get("rejected",False)}
 folder=ROOT/"reviews";folder.mkdir(exist_ok=True)
 path=folder/(candidate_id+"_first_review.json")
 if path.exists():raise RuntimeError("review already exists; do not overwrite")
 path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 return {"verified":True,"report":str(path),"observation":text[:700],
   "quality_approved":False,"model_generated_consistency_proven":False}
