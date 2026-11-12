"""Zero-spend image-to-video router for Jarvis. Only public HF ZeroGPU Spaces.
Never contacts payment endpoints, never uses paid keys, never publishes output.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlparse
import json,os,re,time,mimetypes
import requests

ROOT=Path("H:/LP18")
OUT=ROOT/"renders"/"cloud_videorouter"
OUT.mkdir(parents=True,exist_ok=True)
CATALOG=[
 {"id":"wan14_fast","space":"zerogpu-aoti/wan2-2-fp8da-aoti-faster",
  "host":"zerogpu-aoti-wan2-2-fp8da-aoti-faster.hf.space","api":"/generate_video","type":"i2v","cost_usd":0,"watermark":"unverified"},
 {"id":"wan_r3gm","space":"r3gm/wan2-2-fp8da-aoti-preview",
  "host":"r3gm-wan2-2-fp8da-aoti-preview.hf.space","api":"/generate_video","type":"i2v","cost_usd":0,"watermark":"unverified"},
 {"id":"wan_kulkas","space":"kulkas2pintu/wan777",
  "host":"kulkas2pintu-wan777.hf.space","api":"/generate_video","type":"i2v","cost_usd":0,"watermark":"unverified"},
 {"id":"svd_xt","space":"Coderados/svd-img2vid-xt",
  "host":"coderados-svd-img2vid-xt.hf.space","api":"/video","type":"i2v","cost_usd":0,"watermark":"unverified"}]
WEB_ONLY=[
 {"id":"rendastic","url":"https://rendastic.com/image-to-video","reason":"no documented public automation API"},
 {"id":"openfilmo","url":"https://www.openfilmo.com/pricing/","reason":"API only on paid Studio plan"},
 {"id":"free_ai","url":"https://free.ai/docs/","reason":"web daily free pool does not apply to API calls"},
 {"id":"videorouter_sh","url":"https://videorouter.sh/docs/pricing-billing","reason":"prepaid paid API"}]

def _info(p,timeout=7):
 url="https://"+p["host"]+"/gradio_api/info"
 r=requests.get(url,timeout=timeout)
 r.raise_for_status()
 data=r.json().get("named_endpoints",{})
 if p["api"] not in data:raise RuntimeError("missing_declared_api")
 return list(x.get("parameter_name") for x in data[p["api"]].get("parameters",[]))

def status(check_network=False):
 items=[]
 for p in CATALOG:
  item={k:v for k,v in p.items() if k not in ("host",)}
  item["ready"]="unverified"
  if check_network:
   try:
    par=_info(p)
    item["ready"]="reachable"
    item["parameter_names"]=par
   except Exception as exc:item["ready"]="offline_or_changed";item["error"]=type(exc).__name__
  items.append(item)
 return {"verified":True,"status":"READY_FOR_PILOT" if any(x["ready"]=="reachable" for x in items) else "NEEDS_REMOTE_TEST",
         "mode":"FREE_ONLY_NO_PAID_BACKENDS","zero_spend_hard_limit_usd":0,
         "watermark_policy":"candidate_only_until_visual_check","providers":items,
         "manual_web_only":WEB_ONLY,"output_dir":str(OUT)}

class QuotaError(Exception):pass

def _safe_image(image_path):
 p=Path(image_path).resolve()
 allowed=[(ROOT/"assets").resolve(),(ROOT/"shots").resolve(),
    Path("H:/RealJarvis/OptionalPlugins/JarvisGodot2D/LaliPooli2D_Pilot/studio_library/character_database/masters").resolve()]
 if not any(p.is_relative_to(a) for a in allowed):raise ValueError("image_outside_approved_asset_library")
 if p.suffix.lower() not in (".png",".jpg",".jpeg",".webp") or not p.is_file() or p.stat().st_size>10_000_000:
  raise ValueError("unsupported_image_or_size")
 return p

def _upload(p,image):
 mime=mimetypes.guess_type(str(image))[0] or "image/png"
 base="https://"+p["host"]
 with image.open("rb") as f:
  r=requests.post(base+"/gradio_api/upload",files={"files":(image.name,f,mime)},timeout=45)
 if r.status_code in (401,403,429):raise QuotaError("upload_quota_or_auth")
 r.raise_for_status()
 paths=r.json()
 if not isinstance(paths,list) or not paths or not isinstance(paths[0],str):raise RuntimeError("unexpected_upload_response")
 return {"path":paths[0],"meta":{"_type":"gradio.FileData"}}

def _payload(p,file,txt,seconds):
 if p["id"]=="wan14_fast":
  return [file,txt,6,"blurry, distorted face, extra limbs, watermark, logo, subtitles",float(seconds),1,1,42,False]
 if p["id"] in ("wan_r3gm","wan_kulkas"):
  result=[file,None,txt,6,"blurry, distorted face, extra limbs, watermark, logo, subtitles",float(seconds),1,1,42,False,6,"UniPCMultistep",3.0,"16",True,True]
  if p["id"]=="wan_r3gm":result.append(True)
  return result
 if p["id"]=="svd_xt":
  return [file,42,False,127,7,"25"]
 raise ValueError("provider_not_allowed")

def _result_url(raw,host):
 # Gradio SSE data can contain nested FileData and video entries.
 urls=[]
 def visit(v):
  if isinstance(v,dict):
   if isinstance(v.get("url"),str):urls.append(v["url"])
   for x in v.values():visit(x)
  elif isinstance(v,list):
   for x in v:visit(x)
 visit(raw)
 for u in urls:
  parsed=urlparse(u)
  if parsed.scheme=="https" and parsed.hostname==host and parsed.path and "video" not in parsed.query.lower():
   return u
 raise RuntimeError("missing_safe_video_url")

def _submit(p,image,prompt,seconds):
 base="https://"+p["host"]
 file=_upload(p,image)
 resp=requests.post(base+"/gradio_api/call"+p["api"],json={"data":_payload(p,file,prompt,seconds)},timeout=30)
 if resp.status_code in (401,403,429):raise QuotaError("submit_quota_or_auth")
 resp.raise_for_status()
 event=resp.json().get("event_id")
 if not isinstance(event,str) or not re.fullmatch(r"[\w-]{6,120}",event):raise RuntimeError("invalid_job_id")
 return base+"/gradio_api/call"+p["api"]+"/"+event

def _wait(p,event_url,max_wait=270):
 r=requests.get(event_url,headers={"Accept":"text/event-stream"},stream=True,timeout=(12,60))
 if r.status_code in (401,403,429):raise QuotaError("generation_quota_or_auth")
 r.raise_for_status()
 began=time.monotonic()
 event=""
 try:
  for b in r.iter_lines(decode_unicode=True):
   if time.monotonic()-began>max_wait:raise TimeoutError("generation_timeout")
   if not b:continue
   if b.startswith("event:"):event=b[6:].strip()
   elif b.startswith("data:"):
    try:payload=json.loads(b[5:].strip())
    except ValueError:continue
    if event=="error":
     msg=json.dumps(payload,ensure_ascii=False)[:300].lower()
     if any(k in msg for k in ("quota","limit","not enough","exceeded","gpu")):raise QuotaError("remote_free_quota_exhausted")
     if "404" in msg and "not found" in msg:raise RuntimeError("terminal_gradio_404")
     raise RuntimeError("remote_video_failed")
    if event=="complete":return _result_url(payload,p["host"])
 finally:r.close()
 raise RuntimeError("generation_not_completed")

def _download(p,url):
 name=p["id"]+"_"+datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")+".mp4"
 output=OUT/name
 with requests.get(url,stream=True,timeout=(10,90)) as r:
  r.raise_for_status()
  with output.open("wb") as f:
   for chunk in r.iter_content(65536):
    if chunk:f.write(chunk)
    if f.tell()>100_000_000:
     output.unlink(missing_ok=True)
     raise RuntimeError("video_too_large")
 if output.stat().st_size<12000 or output.read_bytes()[:4] != b"\x00\x00\x00\x18" and b"ftyp" not in output.open("rb").read(64):
  output.unlink(missing_ok=True)
  raise RuntimeError("invalid_mp4")
 return str(output)

def generate(image_path,prompt,seconds=3,execute=False):
 image=_safe_image(image_path)
 if not isinstance(prompt,str) or not 5<=len(prompt)<=500:raise ValueError("prompt_length")
 if not isinstance(seconds,(int,float)) or not 2<=seconds<=5:raise ValueError("duration_out_of_range")
 if not execute:
  return {"verified":True,"submitted":False,"dry_run":True,"image_path":str(image),
          "providers":[x["id"] for x in CATALOG],"charge_usd":0,"reason":"owner_approval_required_for_external_upload"}
 attempts=[]
 for p in CATALOG:
  try:
   params=_info(p)
   if not params:raise RuntimeError("missing_api_parameters")
   event=_submit(p,image,prompt,seconds)
   # Once a job is accepted do not re-submit to another provider on timeout.
   try:
    url=_wait(p,event)
    file=_download(p,url)
    return {"verified":True,"submitted":True,"file":file,"provider":p["id"],
            "watermark_verified":False,"quality_verified":False,"charge_usd":0,"publish_allowed":False}
   except QuotaError as exc:
    attempts.append({"provider":p["id"],"result":"confirmed_quota_rejected","reason":str(exc)})
    continue
   except RuntimeError as exc:
    if str(exc) in ("terminal_gradio_404","remote_video_failed"):
     attempts.append({"provider":p["id"],"result":"confirmed_terminal_failure","reason":str(exc)})
     continue
    return {"verified":True,"submitted":True,"provider":p["id"],"state":"pending_or_failed",
            "job_status_url":event,"error":str(exc)[:180],"attempts":attempts,"publish_allowed":False}
   except Exception as exc:
    return {"verified":True,"submitted":True,"provider":p["id"],"state":"pending_or_failed",
            "job_status_url":event,"error":str(exc)[:180],"attempts":attempts,"publish_allowed":False}
  except QuotaError as exc:
   attempts.append({"provider":p["id"],"result":"quota_or_auth_rejected","reason":str(exc)})
  except (requests.RequestException,RuntimeError,ValueError) as exc:
   attempts.append({"provider":p["id"],"result":"unavailable","reason":str(exc)[:140]})
 return {"verified":True,"submitted":False,"state":"NO_FREE_PROVIDER_AVAILABLE","attempts":attempts,
         "charge_usd":0,"publish_allowed":False}

