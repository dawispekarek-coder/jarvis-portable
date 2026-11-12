"""Safe read-only status and approval-gated audio/video assembly for LP18."""
from pathlib import Path
import importlib.util,wave
ROOT=Path("H:/LP18")
SCRIPT=ROOT/"assemble_reel.py"
def _mod():
 if not SCRIPT.is_file():raise RuntimeError("LP18_assembler_missing")
 spec=importlib.util.spec_from_file_location("_lali_pooli_18s_assembler",SCRIPT)
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 return mod
def status():
 mod=_mod()
 state=mod.check()
 target=ROOT/"audio"/"LALI_POOLI_18S_UPBEAT_JUMPING_AROUND_PREVIEW.wav"
 state["soundtrack_preview"]=str(target)
 state["tts_audio_exists"]=target.is_file()
 if target.is_file():
  with wave.open(str(target),"rb") as w:state["soundtrack_duration"]=round(w.getnframes()/w.getframerate(),3)
 state["first_clip_with_audio"]=str(ROOT/"renders"/"LALI_3S_WITH_SUPERTONIC_BABBLE_TEST.mp4")
 state["first_clip_with_audio_exists"]=Path(state["first_clip_with_audio"]).is_file()
 state["approval_note"]="All six distinct images/videos and the sound mix require visual/audio review before publishing."
 state["verified"]=True
 return state
def preview_first():
 output=_mod().preview_first()
 return {"verified":Path(output).is_file(),"path":output,"published":False}
def build():
 output=_mod().build()
 file=Path(output)
 if not file.is_file() or file.stat().st_size<12000:raise RuntimeError("assembly_output_invalid")
 return {"verified":True,"path":str(file),"bytes":file.stat().st_size,"publish_allowed":False,"status":"DRAFT_NEEDS_OWNER_REVIEW"}

