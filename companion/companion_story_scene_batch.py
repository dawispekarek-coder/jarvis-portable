"""Jarvis native tool: execute exactly nine storyboard still illustrations via existing WanGP.
No Godot, no RAM thresholds, no publishing or image approvals.
"""
from pathlib import Path
import subprocess,json,time,sys,os
ROOT=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\studio_library\production_pipeline')
STORY=ROOT/'stories'/'002_prichod_domu'
WORKER=ROOT/'render_9_story_scenes.py'
STATUS=STORY/'scene_render_status.json'
RUN=STORY/'jarvis_scene_runner.json'
LOG=STORY/'jarvis_scene_runner.log'

def status():
 details={}
 try:details=json.loads(STATUS.read_text(encoding='utf-8'))
 except (OSError,ValueError):pass
 try:r=json.loads(RUN.read_text(encoding='utf-8'))
 except (OSError,ValueError):r={}
 pid=r.get('pid');alive=False
 if pid:
  try:import psutil;alive=psutil.pid_exists(pid)
  except Exception:pass
 return {'verified':True,'stage':'images_only','story':'002_prichod_domu','background_process_running':alive,'pid':pid,'progress':details,'review_required':True,'publish_allowed':False,'storyboard':str(STORY/'shotlist_10_scen.json')}

def start():
 if not WORKER.is_file():raise RuntimeError('Missing storyboard renderer')
 s=status()
 if s['background_process_running']:return {**s,'started':False,'reason':'already_running'}
 if s['progress'].get('status')=='FINISHED_REVIEW_REQUIRED':return {**s,'started':False,'reason':'already_finished_do_not_overwrite'}
 path=STORY/'shotlist_10_scen.json'
 if not path.is_file() or len(json.loads(path.read_text(encoding='utf-8')))!=10:raise RuntimeError('Expected exactly 10 approved storyboard instructions')
 f=LOG.open('a',encoding='utf-8')
 try:
  p=subprocess.Popen([sys.executable,str(WORKER)],cwd=str(ROOT),stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS,close_fds=True)
 finally:f.close()
 RUN.write_text(json.dumps({'pid':p.pid,'started_utc':time.time(),'task':'nine_scenes_02_through_10','requested_by':'owner via Jarvis','no_publish':True},indent=2),encoding='utf-8')
 return {'verified':True,'started':True,'pid':p.pid,'status':'STARTED_RENDERING_CANDIDATES_NOT_FINISHED','output_folder':str(STORY),'review_required':True,'publish_allowed':False,'no_godot':True,'no_ram_watchdog':True}
def status_all():
 folder=STORY/'regenerate_all_10_no_scene_anchor'
 file=folder/'scene_render_status.json'
 run=folder/'jarvis_batch_v2_runner.json'
 try:progress=json.loads(file.read_text(encoding='utf-8'))
 except (OSError,ValueError):progress={}
 try:meta=json.loads(run.read_text(encoding='utf-8'))
 except (OSError,ValueError):meta={}
 pid=meta.get('pid');alive=False
 if pid:
  try:import psutil;alive=psutil.pid_exists(pid)
  except Exception:pass
 return {'verified':True,'model':'FLUX2 Klein','story':'002_prichod_domu','new_batch':True,'total_scenes':10,'running':alive,'progress':progress,'pid':pid,'output_folder':str(folder),'reference_mode':'approved_masters_only_no_previous_scene','size_rule':'Pooli>=Lali; Pooli nominally 5-15% taller in equal-depth standing pose','publish_allowed':False}

def regenerate_all():
 from companion_scene_sets import status as set_status
 background=set_status()
 if not background['ready']:
  return {'verified':True,'started':False,'reason':'house_backgrounds_require_owner_review','description':'Pripravuji stabilni kulisy domu. Nez budou overene, nesmim znovu generovat dalsi sceny s menicim se interierem.','sets':background['sets'],'no_publish':True}

 existing=status_all()
 if existing['running']:return {**existing,'started':False,'reason':'already_running'}
 if existing['progress'].get('status')=='FINISHED_REVIEW_REQUIRED':return {**existing,'started':False,'reason':'already_completed_no_overwrite'}
 folder=STORY/'regenerate_all_10_no_scene_anchor';folder.mkdir(parents=True,exist_ok=True)
 worker=ROOT/'render_10_story_scenes_v2.py'
 if not worker.is_file():raise RuntimeError('Verified new worker missing')
 with (folder/'jarvis_batch_v2_runner.log').open('a',encoding='utf-8') as f:
  process=subprocess.Popen([sys.executable,str(worker)],cwd=str(ROOT),stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS,close_fds=True)
 (folder/'jarvis_batch_v2_runner.json').write_text(json.dumps({'pid':process.pid,'started_utc':time.time(),'source':'Jarvis UI command','only_candidates':True,'references':'original approved master images only','size_rule':'Pooli larger or equal','no_scene01_reference':True,'publish_allowed':False},indent=2),encoding='utf-8')
 return {'verified':True,'started':True,'status':'RUNNING_NOT_FINISHED','pid':process.pid,'total_scenes':10,'output_folder':str(folder),'reference_mode':'approved_masters_only_no_scene1','size_rule':'Pooli >= Lali','no_publish':True,'review_required':True}