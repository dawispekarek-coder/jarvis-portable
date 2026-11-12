"""Read-only, credit-safe Dreamina First-Frame Lali & Pooli production plan.
Never calls Dreamina or spends credits. Final output must be visually reviewed.
"""
from pathlib import Path
import json,hashlib
ROOT=Path("H:/LP18/DreaminaStartOnly_20261029")
PLAN=ROOT/"dreamina_shot_plan.json"
def status():
    if not PLAN.is_file():return {"verified":True,"ready":False,"reason":"plan_missing"}
    data=json.loads(PLAN.read_text(encoding="utf-8-sig"))
    path=Path(data.get("start_image",""));text=Path(data.get("prompt_file",""))
    checks={
        "start_image_exists":path.is_file(),
        "prompt_exists":text.is_file(),
        "single_start_frame":data.get("no_multiframes") is True and data.get("no_end_image") is True,
        "model_mini":data.get("model")=="Dreamina Seedance 2.0 Mini",
        "under_budget":int(data.get("verified_price_credits",9999)) <=int(data.get("credit_hard_cap_per_render",0)),
        "publish_blocked":data.get("publish_allowed") is False
    }
    if path.is_file():checks["start_sha256_ok"]=hashlib.sha256(path.read_bytes()).hexdigest()==data.get("start_image_sha256")
    result={"verified":True,"ready":all(checks.values()),"checks":checks,"state":data.get("state"),
            "workflow":"First frame ONLY, English motion prompt, 15s 9:16 720p; NEVER Multiframes or generic Omni reference",
            "model":data.get("model"),"start_image":str(path),"prompt_file":str(text),
            "current_render_price_credits":data.get("verified_price_credits"),
            "hard_cap_per_render":data.get("credit_hard_cap_per_render"),
            "approval_required_for_new_render":True,"automatic_paid_submissions_allowed":False,
            "workspace_url":data.get("dreamina_workspace_url"),"publish_allowed":False}
    output=data.get("output_mp4")
    report=data.get("motion_qa_report")
    result["output_video_path"]=output if output and Path(output).is_file() else None
    result["motion_qa_path"]=report if report and Path(report).is_file() else None
    result["owner_approved"]=data.get("owner_approved",False)
    result["state_is_completed"]=bool(result["output_video_path"] and result["motion_qa_path"])
    if result["motion_qa_path"]:
        evidence=json.loads(Path(report).read_text(encoding="utf-8"))
        result["independent_actor_motion_evidence"]=bool(evidence.get("independent_actor_motion_evidence",False))
        result["frame_samples_checked"]=evidence.get("sampled_frames",0)
        result["actual_average_fps"]=data.get("actual_average_fps")
    return result
def plan():
    x=status()
    if not x.get("ready"):return x
    prompt=Path(x["prompt_file"]).read_text(encoding="utf-8")
    return {**x,"prompt_preview":prompt[:320],"prompt_chars":len(prompt),
            "manual_steps":"Open user's existing logged-in Dreamina browser, select Seedance 2.0 Mini > First and last frames > upload START only > leave LAST empty > paste prompt > 15s > 720p > portrait source ratio. Visually verify displayed credit amount <=125 AND obtain owner's explicit approval BEFORE a new generation. No payment, no auto-submit, no Instagram posting."}

