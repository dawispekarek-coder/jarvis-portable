"""Reusable original whole-frame Lali/Pooli image-to-video jobs. No puppet/Godot, no auto approval."""
from __future__ import annotations
from pathlib import Path
from PIL import Image
import json,hashlib,subprocess,uuid,psutil
from companion_character_database import search
ROOT=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\studio_library\production_pipeline')
JOBS=ROOT/'jobs'
WAN=Path(r'H:\RealJarvis\OptionalPlugins\WanGP')
PY=WAN/'.venv312'/'Scripts'/'python.exe'
BASE=WAN/'settings'/'lali_object_consistency_33frames.json'
PROMPTS={
 'wave':'One original fluffy cartoon raccoon waves in greeting: the open paw visible on the RIGHT SIDE OF THE IMAGE moves OUTWARD from the shoulder and then BACK near the head, with a real connected elbow and wrist. The other arm at image-left stays DOWN at the side. Show an actual wave not camera motion.',
 'blink':'One original fluffy cartoon raccoon blinks slowly, smiles with natural facial animation, and tilts their head slightly without changing body design or background.',
 'greet':'One original fluffy cartoon raccoon happily greets someone: they lean naturally with attached arms and move an open paw outward, blink and smile. Full body remains visible and feet grounded.'}

def _file(run_id):
 if not isinstance(run_id,str) or len(run_id)!=12 or any(c not in '0123456789abcdef' for c in run_id):raise ValueError('Invalid run ID')
 return JOBS/run_id/'manifest.json'

def _load(run_id):return json.loads(_file(run_id).read_text(encoding='utf-8'))

def _save(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')

def _approved(character,action):
 choices=search(character,status='approved')['items'];ident=character+'_wave_open_working_a' if character=='pooli' and action=='wave' else character+'_master_fullbody'
 found=[x for x in choices if x['id']==ident and x['integrity_valid']]
 if len(found)!=1:raise RuntimeError('Approved character reference missing or corrupt: '+ident)
 item=found[0];src=Path(item['path'])
 if not src.is_file() or hashlib.sha256(src.read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('Approved source modified')
 return item,src
def prepare(character='pooli',action='wave',frames=17):
 if character not in ('pooli','lali') or action not in PROMPTS or type(frames) is not int or frames not in (17,33):raise ValueError('Unsupported whole-shot request')
 if not PY.is_file() or not BASE.is_file():raise RuntimeError('Local WanGP missing')
 item,src=_approved(character,action)
 run_id=uuid.uuid4().hex[:12];work=JOBS/run_id;work.mkdir(parents=True,exist_ok=False)
 with Image.open(src) as image:
  image=image.convert('RGBA');image.thumbnail((288,406),Image.Resampling.LANCZOS)
  bg=Image.new('RGBA',(288,512),(247,228,206,255));bg.alpha_composite(image,((288-image.width)//2,(512-image.height)//2));out=bg.convert('RGB')
 anchor=work/'start.png';out.save(anchor)
 description=('same Pooli dark brown cartoon raccoon with backward blue cap, blue hoodie, cream belly, huge brown eyes, striped fluffy tail' if character=='pooli' else 'same Lali girl raccoon with pink hair bow, original face mask and body proportions')
 prompt='One coherent WHOLE BODY hand-drawn 2D original character animation of the '+description+'. '+PROMPTS[action]+' Preserve EXACT approved identity and clothes, every paw and both feet, tail separate, cohesive full body in frame. Beige plain background, static camera, no extra limbs, subtitles, objects, cropping or cutout puppets.'
 cfg=json.loads(BASE.read_text(encoding='utf-8'));cfg.update({'model_type':'fun_inp_1.3B','image_prompt_type':'S','video_prompt_type':'','image_start':str(anchor),'image_end':'','image_refs':'','resolution':'288x512','video_length':frames,'num_inference_steps':20,'seed':744230865,'prompt':prompt,'batch_size':1,'output_filename':'LP_'+character.upper()+'_'+action.upper()+'_'+run_id})
 config=work/'settings.json';_save(config,cfg)
 manifest={'run_id':run_id,'character':character,'action':action,'frames':frames,'model':'fun_inp_1.3B','image_prompt_type':'S','approved_source_id':item['id'],'approved_source_sha256':item['sha256'],'anchor':str(anchor),'config':str(config),'output':str(work/(cfg['output_filename']+'.mp4')),'status':'PREPARED_NOT_RENDERED','review_required':True,'quality_approved':False,'publish_allowed':False}
 _save(work/'manifest.json',manifest)
 return {'verified':True,'status':'PREPARED_NOT_RENDERED','run_id':run_id,'source_asset':item['id'],'settings':str(config),'frames':frames,'mode':'S','approval':False}
def start(run_id):
 m=_load(run_id)
 if m['status']!='PREPARED_NOT_RENDERED':return {'verified':False,'status':m['status'],'run_id':run_id}
 item,src=_approved(m['character'],m['action'])
 if item['id']!=m['approved_source_id'] or item['sha256']!=m['approved_source_sha256']:raise RuntimeError('Source no longer approved')
 config=Path(m['config']);cfg=json.loads(config.read_text(encoding='utf-8'))
 if cfg.get('image_prompt_type')!='S' or cfg.get('model_type')!='fun_inp_1.3B' or cfg.get('image_start')!=m['anchor']:raise RuntimeError('Image condition flag or source changed')
 for proc in psutil.process_iter(['cmdline']):
  try:args=' '.join(proc.info.get('cmdline') or []).lower()
  except psutil.Error:continue
  if 'wgp.py' in args and '--process' in args:return {'verified':False,'status':'ANOTHER_VIDEO_RENDER_ACTIVE','run_id':run_id}
 work=_file(run_id).parent;log=work/'render.log'
 with log.open('wb') as stream:
  child=subprocess.Popen([str(PY),str(WAN/'wgp.py'),'--process',str(config),'--output-dir',str(work)],cwd=str(WAN),stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0))
 m['status']='STARTED_UNAPPROVED';m['pid']=child.pid;m['log']=str(log);_save(_file(run_id),m)
 return {'verified':True,'status':m['status'],'run_id':run_id,'pid':child.pid,'log':str(log),'review_required':True}
def status(run_id=''):
 if not run_id:
  files=sorted(JOBS.glob('*/manifest.json'),key=lambda a:a.stat().st_mtime,reverse=True)
  if not files:return {'verified':True,'status':'NO_JOBS','ready_for_publish':False}
  run_id=files[0].parent.name
 m=_load(run_id)
 pid=m.get('pid');alive=False
 if pid and psutil.pid_exists(pid):
  try:alive='wgp.py' in ' '.join(psutil.Process(pid).cmdline()).lower()
  except psutil.Error:pass
 output=Path(m['output']);qa=output.with_suffix('.qa.json')
 if alive:m['status']='RENDERING_UNAPPROVED'
 elif pid and output.is_file() and output.stat().st_size>10000:
  if not qa.exists():
   process=subprocess.run([str(PY),str(ROOT/'inspect_video.py'),str(output)],capture_output=True,text=True,timeout=50)
   m['qa_command_exit']=process.returncode
  m['status']='GENERATED_NEEDS_VISUAL_QA' if qa.is_file() else 'GENERATED_QA_ERROR'
 elif pid:m['status']='FAILED_NO_VIDEO'
 _save(_file(run_id),m)
 detail=json.loads(qa.read_text(encoding='utf-8')) if qa.is_file() else {}
 return {'verified':True,'run_id':run_id,'status':m['status'],'character':m['character'],'action':m['action'],'output_video':str(output) if output.exists() else None,'source_asset':m['approved_source_id'],'technical_qa':detail,'quality_approved':False,'publish_allowed':False,'log':m.get('log'),'running':alive}
def create(character='pooli',action='wave',frames=17):
 """One user command prepares a locked approved scene and starts a whole-frame draft."""
 prepared=prepare(character,action,frames)
 started=start(prepared['run_id'])
 return {**started,'source_asset':prepared['source_asset'],'settings':prepared['settings'],'frames':frames,'video_not_yet_finished':True,'quality_approved':False,'publish_allowed':False}