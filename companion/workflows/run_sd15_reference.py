from pathlib import Path
import json,sys,time,uuid,urllib.request,urllib.parse
from safetensors import safe_open
who=sys.argv[1] if len(sys.argv)>1 else 'pooli'
if who not in ('lali','pooli'):raise ValueError('Unknown character')
base=Path(__file__).parent
model=Path(r'H:\RealJarvis\OptionalPlugins\ComfyUI\models\checkpoints\sd15-pruned-emaonly.safetensors')
if not model.is_file() or model.stat().st_size!=4265146304:raise RuntimeError('Checkpoint incomplete')
with safe_open(str(model),framework='pt',device='cpu') as f:
 if len(f.keys())<1000:raise RuntimeError('Checkpoint tensors invalid')
wf=json.loads((base/f'sd15_{who}_reference_api.json').read_text(encoding='utf-8'))
manifest=json.loads((base/f'sd15_{who}_manifest.json').read_text(encoding='utf-8'))
if not Path(manifest['input_copy']).is_file():raise RuntimeError('Reference input missing')
def api(path,data=None):
 req=urllib.request.Request('http://127.0.0.1:8188'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'} if data is not None else {})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
pid=api('/prompt',{'prompt':wf,'client_id':'jarvis-reference-study'})['prompt_id']
print('submitted='+pid,flush=True)
for i in range(240):
 time.sleep(3)
 h=api('/history/'+pid)
 if pid not in h:continue
 item=h[pid]
 if item.get('status',{}).get('status_str')=='error':raise RuntimeError(str(item['status']))
 imgs=item.get('outputs',{}).get('8',{}).get('images',[])
 if not imgs:continue
 im=imgs[0];q=urllib.parse.urlencode({'filename':im['filename'],'subfolder':im.get('subfolder',''),'type':'output'})
 with urllib.request.urlopen('http://127.0.0.1:8188/view?'+q,timeout=30) as r:raw=r.read()
 out=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\training\wholeframe_experiments\provider_studies');out.mkdir(parents=True,exist_ok=True)
 name=f'{who}_front_{uuid.uuid4().hex[:12]}.png';dst=out/name
 with dst.open('xb') as f:f.write(raw)
 result={'image':str(dst),'character':who,'reference_used':True,'approved':False,'publish_allowed':False,'animation_ready':False,'prompt_id':pid}
 dst.with_suffix('.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result),flush=True);break
else:raise TimeoutError('ComfyUI generation timed out')
