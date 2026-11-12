"""Jarvis -> official WanGP Python API bridge. No model downloads on import."""
import json,sys
from pathlib import Path
WANGP=Path(r"H:\RealJarvis\OptionalPlugins\WanGP")
SOURCE=Path(r"H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\studio_library\trace_from_approved_8panels\approved_eight_panel_storyboard.png")
def status():
    return {"repo":str(WANGP),"repo_present":(WANGP/"wgp.py").is_file(),"api_present":(WANGP/"shared"/"api.py").is_file(),"reference_present":SOURCE.is_file(),"runtime_ready":False,"model_tested":False,"note":"Runtime not installed yet. No video generated."}
def generate(settings_path):
    if not SOURCE.is_file(): raise RuntimeError("Approved reference missing")
    if not (WANGP/"shared"/"api.py").is_file(): raise RuntimeError("WanGP source/API missing")
    sys.path.insert(0,str(WANGP))
    from shared.api import init
    settings=json.loads(Path(settings_path).read_text(encoding="utf-8"))
    if not isinstance(settings,dict): raise ValueError("Expected WanGP exported settings JSON object")
    session=init(root=WANGP,cli_args=["--attention","sdpa"])
    job=session.submit_task(settings)
    result=job.result()
    print(json.dumps({"success":result.success,"files":[str(x) for x in (result.generated_files or [])],"errors":[str(x.message) for x in (result.errors or [])]},ensure_ascii=False))
    return bool(result.success)
if __name__=="__main__":
    if len(sys.argv)==1 or sys.argv[1]=="status": print(json.dumps(status(),indent=2))
    elif sys.argv[1]=="generate" and len(sys.argv)==3: sys.exit(0 if generate(sys.argv[2]) else 1)
    else: raise SystemExit("Usage: jarvis_wangp_bridge.py status | generate exported_wangp_settings.json")
