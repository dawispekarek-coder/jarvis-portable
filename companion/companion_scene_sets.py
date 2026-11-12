"""Immutable scene-set evidence and approval gates for the Lali/Pooli universe."""
import hashlib,json
from pathlib import Path
BASE=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\studio_library\production_pipeline\sets\house_v1')
SETS=('living_room','hallway','front_exterior')

def status():
 p=BASE/'house_layout.json'
 if not p.is_file():return {'verified':False,'ready':False,'error':'House set bible missing'}
 m=json.loads(p.read_text(encoding='utf-8'))
 data={}
 for name in SETS:
  d=m['canonical_sets'][name]
  file=BASE/d['background']
  actual=hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None
  data[name]={'status':d['status'],'file':str(file),'exists':file.is_file(),'hash_matches':bool(actual and d.get('sha256') and actual==d['sha256']),'approved':d['status']=='OWNER_APPROVED_MASTER'}
 ready=all(row['exists'] and row['approved'] and row['hash_matches'] for row in data.values())
 return {'verified':True,'ready':ready,'sets':data,'source_scene':m['source_scene'],'identity_scale_rule':m['scale_rule'],'manual_approval_required':not ready,'publish_allowed':False}

def require_ready():
 result=status()
 if not result.get('ready'):
  missing=[n for n,d in result.get('sets',{}).items() if not d['approved'] or not d['hash_matches']]
  raise RuntimeError('STOP: Scene-set consistency not approved; cannot generate 10 new scenes. Missing: '+', '.join(missing))
 return result