"""Pooli Blender modelling draft worker for Jarvis 2.1.
Only produces isolated, UNAPPROVED meshes. No publishing or master promotion.
"""
from __future__ import annotations
import hashlib,json,subprocess
from pathlib import Path

ROOT=Path(r"H:\RealJarvis\OptionalPlugins\JarvisBlender3D\PooliReferenceModelV4")
BLENDER=Path(r"H:\RealJarvis\OptionalPlugins\Blender4.5LTS\blender-4.5.15-windows-x64\blender.exe")
SCRIPT=ROOT/"enhance_pooli_fur.py"
AUDIT=ROOT/"audit_fur_tail.py"
REFERENCE=Path(r"H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\studio_library\refs\pooli\fullbody.png")
REQUIRED={
 "blend":ROOT/"Pooli_FurryTail_DRAFT.blend",
 "glb":ROOT/"Pooli_FurryTail_DRAFT.glb",
 "front":ROOT/"pooli_front.png",
 "three_quarter":ROOT/"pooli_three_quarter.png",
 "side":ROOT/"pooli_side.png",
 "back":ROOT/"pooli_back.png"
}
def status():
    checks={key:{"present":path.is_file(),"bytes":path.stat().st_size if path.is_file() else 0}
            for key,path in REQUIRED.items()}
    report_file=ROOT/"model_report.json"
    report={}
    if report_file.is_file():
        try:report=json.loads(report_file.read_text(encoding="utf8"))
        except (ValueError,OSError):report={"invalid_report":True}
    topofile=ROOT/"fur_tail_qa.json"
    topology={}
    topology_fresh=bool(topofile.is_file() and REQUIRED["blend"].is_file() and topofile.stat().st_mtime>=REQUIRED["blend"].stat().st_mtime)
    if topology_fresh:
        try:topology=json.loads(topofile.read_text(encoding="utf8"))
        except (ValueError,OSError):topology={}
    def connected(key):
        labels={"POOLI_CONNECTED_HEAD__single_fused_mesh":"head",
                "POOLI_CONNECTED_BLUE_HOODIE_AND_SLEEVES":"hoodie",
                "POOLI_CONNECTED_LOWER_FUR_BODY_AND_FEET":"lower",
                "POOLI_CURLING_STRIPED_FURRY_TAIL":"tail"}
        entry=topology.get("geometry",{}).get(labels.get(key,""),{})
        return bool(topology_fresh and entry.get("one_continuous_mesh") is True)
    complete=all(d["present"] and d["bytes"]>1000 for d in checks.values())
    ref_hash=hashlib.sha256(REFERENCE.read_bytes()).hexdigest() if REFERENCE.is_file() else None
    return {"verified":True,"blender_available":BLENDER.is_file(),
       "reference_available":REFERENCE.is_file(),"reference_sha256":ref_hash,
       "script_available":SCRIPT.is_file(),"draft_artifacts_ready":complete,
       "files":checks,"geometry":report,"topology":topology,"scene_path":str(REQUIRED["blend"]),
       "godot_glb_path":str(REQUIRED["glb"]),
       "qa":{"head_connected_mesh":connected("POOLI_CONNECTED_HEAD__single_fused_mesh"),
             "hoodie_and_sleeves_connected_mesh":connected("POOLI_CONNECTED_BLUE_HOODIE_AND_SLEEVES"),
             "lower_body_connected_mesh":connected("POOLI_CONNECTED_LOWER_FUR_BODY_AND_FEET"),
             "multi_angle_renders_ready":all(checks[k]["present"] for k in ("front","side","back")),
             "tail_connected_mesh":connected("POOLI_CURLING_STRIPED_FURRY_TAIL"),
             "fur_strands_present":bool(topology_fresh and all(topology.get("hair",{}).get(k,{}).get("strands",0)>=1000 for k in ("head","haunches","tail"))),
             "tail_framed_in_all_views":bool(topology_fresh and all(topology.get("framing",{}).get(k,{}).get("tail_mesh_within_frame") is True for k in ("front","three_quarter","side","back"))),
             "visual_matches_reference":None,
             "professional_quality_approved":False,
             "fully_rigged":False,
             "owner_approval_required":True},
       "next_required":"Open Blender draft and compare front side back to canonical Pooli master. Fix deviations, then rig before animation. Never publish."}
def generate():
    if not BLENDER.is_file() or not SCRIPT.is_file() or not REFERENCE.is_file():
        raise RuntimeError("Blender, bounded build script or original reference missing")
    s=status()
    if s["draft_artifacts_ready"]:return dict(s,reused=True,generated_now=False)
    proc=subprocess.run([str(BLENDER),"--background","--python",str(SCRIPT)],
                        cwd=str(ROOT),capture_output=True,text=True,timeout=240,check=False)
    if proc.returncode:
        raise RuntimeError("Blender failed: "+(proc.stderr+"\n"+proc.stdout)[-1800:])
    if AUDIT.is_file() and REQUIRED["blend"].is_file():
        audit=subprocess.run([str(BLENDER),"--background",str(REQUIRED["blend"]),"--python",str(AUDIT)],
                             cwd=str(ROOT),capture_output=True,text=True,timeout=120,check=False)
        if audit.returncode:raise RuntimeError("Topology QA failed: "+audit.stderr[-1200:])
    result=status()
    if not result["draft_artifacts_ready"]:
        raise RuntimeError("Blender returned success without verified 4-view artifacts: "+proc.stdout[-1400:])
    return dict(result,reused=False,generated_now=True)

