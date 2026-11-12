from pathlib import Path
import json,sys,time,uuid,urllib.request,urllib.parse
root=Path(__file__).parent
who=sys.argv[1] if len(sys.argv)>1 else 'pooli'
if who!='pooli':raise ValueError('Only pooli test configured')
wf=json.loads((root/'sd15_pooli_pastel_test_api.json').read_text(encoding='utf-8-sig'))
def api(path,data=None):
 req=urllib.request.Request('http://127.0.0.1:8188'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'} if data is not None else {})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
pid=api('/prompt',{'prompt':wf,'client_id':'jarvis-pastel-style-test'})['prompt_id']
print('submitted='+pid,flush=True)
for i in range(180):
 time.sleep(3);h=api('/history/'+pid)
 if pid not in h:continue
 item=h[pid]
 if item.get('status',{}).get('status_str')=='error':raise RuntimeError(str(item['status']))
 imgs=item.get('outputs',{}).get('8',{}).get('images',[])
 if not imgs:continue
 im=imgs[0];q=urllib.parse.urlencode({'filename':im['filename'],'subfolder':im.get('subfolder',''),'type':'output'})
 with urllib.request.urlopen('http://127.0.0.1:8188/view?'+q,timeout=30) as r:raw=r.read()
 out=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\training\wholeframe_experiments\provider_studies')
 dst=out/('pooli_pastel_style_test_'+uuid.uuid4().hex[:8]+'.png');dst.write_bytes(raw)
 print(json.dumps({'candidate':str(dst),'approved':False,'style_test':True}),flush=True)
 break
else:raise TimeoutError('Pastel style test timed out')

