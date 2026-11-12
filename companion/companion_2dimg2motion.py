"""Full-body 2dimg2motion pipeline. Cannot draw frames without an image model."""
from pathlib import Path
from PIL import Image
import json, shutil, hashlib, re, sys, subprocess, uuid
from urllib.request import urlopen

UPSTREAM = Path(r"H:\RealJarvis\OptionalPlugins\2dimg2motion")
GODOT = Path(r"H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot")
WORK = GODOT / "training" / "wholeframe_experiments"
REFS = {c: GODOT/"assets"/"sprites"/(c+"_official_fullpose_cutout.png") for c in ("lali","pooli")}
MOVES = {
 "walk": "contact, down, passing, up, opposite contact, passing; clear alternate limbs",
 "turn": "front, three-quarter, profile, rear-three-quarter, back; fully redraw anatomical views",
 "sit": "stand, anticipation, bend, sit, settle; real posture, no sliding",
}
def _folder(run_id):
 if not re.fullmatch(r"(lali|pooli)_(walk|turn|sit)_[0-9a-f]{12}",run_id or ""):
  raise ValueError("invalid run id")
 return WORK/run_id
def status():
 try:
  with urlopen("http://127.0.0.1:5688/health",timeout=2) as r:
   krita=json.loads(r.read()).get("status")=="ok"
 except Exception: krita=False
 return {"verified":True,"skill_installed":(UPSTREAM/"SKILL.md").is_file(),
  "validator_installed":(UPSTREAM/"scripts"/"validate_14frame_pattern.py").is_file(),
  "references_available":{k:v.is_file() for k,v in REFS.items()},
  "godot_ready":(GODOT/"project.godot").is_file(),"krita_mcp_live":krita,
  "image_generator_configured":__import__("companion_image_provider").local_comfy_status().get("online",False),"professional_animation_completed":False,
  "blocker":"Local ComfyUI image provider available, but consistent reference-conditioned 14-frame animation unverified",
  "scope":"infrastructure status, not proof of creative quality"}
def prepare(character="lali",movement="walk"):
 if character not in REFS or movement not in MOVES:raise ValueError("unknown character or motion")
 src=REFS[character]
 if not src.is_file() or not (UPSTREAM/"SKILL.md").is_file():raise RuntimeError("reference or skill missing")
 with Image.open(src) as im:
  if im.mode!="RGBA" or im.getbbox() is None:raise ValueError("baseline must be nonempty RGBA")
 run_id=character+"_"+movement+"_"+uuid.uuid4().hex[:12]
 p=_folder(run_id);p.mkdir(parents=True)
 for sub in ("fullframe","keyframe"): (p/sub).mkdir()
 shutil.copy2(src,p/"baseline.png")
 info={"run_id":run_id,"character":character,"movement":movement,
  "original_reference":str(src),"reference_sha256":hashlib.sha256(src.read_bytes()).hexdigest(),
  "image_generator":"UNCONFIGURED","generated_frames":0,"frame_count":14,
  "keyframes":[2,5,8,11],"approved":False,"publish_allowed":False}
 (p/"manifest.json").write_text(json.dumps(info,indent=2),encoding="utf-8")
 prompt=f"""Use https://github.com/WU-HAOTIAN34/2dimg2motion SKILL.md and references/keypose-redraw.md.
Source: {src}. Character {character}, motion {movement}: {MOVES[movement]}
Draw FOUR NEW entire-body keyposes 02/05/08/11 plus full-body inbetween frames.
Fourteen RGBA transparent individual PNG frames with identical full-body identity,
feet aligned, no ears/tail/feet cropped, same clothing, eyes and colors.
Do not use layer segmentation, SVG/Pillow drawings, cutout rigs or image warping.
Full turns require genuinely new side and rear drawings; no flat sprite rotation.
Place frames in fullframe/{character}_{movement}_00.png ... _13.png.
Put exact copies of frames 02/05/08/11 in keyframe/ of same names.
Frame 00 is original unchanged fullbody; frame 13 byte-identical to 00.
Review every frame and preview visually; structural validation is not visual approval.
IMPORTANT: Image generation provider is NOT CONFIGURED in Jarvis. Never claim images exist.
Do not use old Godot Stage2/Stage3; no Instagram publishing.
"""
 (p/"drawing_brief.txt").write_text(prompt,encoding="utf-8")
 return {"verified":True,"run_id":run_id,"workspace":str(p),"instructions":str(p/"drawing_brief.txt"),
         "prepared":True,"generated_frames":0,"blocked_by_missing_image_generator":True}
def validate(run_id):
 p=_folder(run_id)
 if not (p/"manifest.json").is_file():raise ValueError("unknown run")
 info=json.loads((p/"manifest.json").read_text(encoding="utf-8"))
 prefix=info["character"]+"_"+info["movement"]
 missing=[f"{prefix}_{i:02d}.png" for i in range(14) if not (p/"fullframe"/f"{prefix}_{i:02d}.png").is_file()]
 if missing:  return {"verified":False,"technical_validated":False,"quality_approved":False,
          "frames_present":14-len(missing),"missing_frames":missing,"reason":"No real generated frames"}
 gif=p/"preview.gif"
 if not gif.is_file():
  job=subprocess.run([sys.executable,str(UPSTREAM/"scripts"/"fullframes_to_gif.py"),
    str(p/"fullframe"),"--output",str(gif),"--pattern",prefix+"_*.png"],text=True,
    capture_output=True,timeout=60)
  if job.returncode:return {"verified":False,"reason":"preview failed","error":job.stderr[-1200:]}
 sys.path.insert(0,str(UPSTREAM/"scripts"))
 from validate_14frame_pattern import validate_pattern
 errors=validate_pattern(baseline=p/"baseline.png",keyframes_dir=p/"keyframe",
  fullframes_dir=p/"fullframe",preview=gif,prefix=prefix)
 return {"verified":not errors,"technical_validated":not errors,"quality_approved":False,
  "visual_review_required":True,"errors":errors,"preview":str(gif),
  "scope":"technical validation only; no permission to publish"}
def import_godot(run_id):
 result=validate(run_id)
 if not result.get("technical_validated"):return {**result,"imported":False}
 p=_folder(run_id);info=json.loads((p/"manifest.json").read_text(encoding="utf-8"))
 prefix=info["character"]+"_"+info["movement"]
 dst=GODOT/"assets"/"wholeframes"/run_id
 if dst.exists():raise RuntimeError("refusing to overwrite existing import")
 dst.mkdir(parents=True)
 for f in sorted((p/"fullframe").glob("*.png")):shutil.copy2(f,dst/f.name)
 resources=[f'[ext_resource type="Texture2D" path="res://assets/wholeframes/{run_id}/{prefix}_{i:02d}.png" id="{i+1}"]' for i in range(14)]
 frame_items=", ".join(f'{{"duration": 1.0, "texture": ExtResource("{i+1}")}}' for i in range(14))
 scene='[gd_scene load_steps=16 format=3]\n\n'+"\n".join(resources)
 scene+='\n\n[sub_resource type="SpriteFrames" id="1"]\nanimations = [{"frames": ['
 scene+=frame_items+'], "loop": true, "name": &"'+info["movement"]+'", "speed": 12.0}]\n'
 scene+='\n[node name="WholeFrameScene" type="Node2D"]\n'
 scene+='[node name="Character" type="AnimatedSprite2D" parent="."]\n'
 scene+='sprite_frames = SubResource("1")\nanimation = &"'+info["movement"]+'"\nplaying = true\n'
 scenes=GODOT/"scenes"/"wholeframes";scenes.mkdir(exist_ok=True)
 out=scenes/(run_id+".tscn")
 if out.exists():raise RuntimeError("refusing to overwrite existing scene")
 out.write_text(scene,encoding="utf-8")
 return {"verified":out.is_file(),"imported":True,"fullbody_frames":14,
  "godot_scene":str(out),"visual_quality_approved":False,"publish_allowed":False}
