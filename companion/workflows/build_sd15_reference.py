from pathlib import Path
from PIL import Image
import hashlib,json,io
root=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\studio_library\refs')
comfy=Path(r'H:\RealJarvis\OptionalPlugins\ComfyUI')
out=Path(__file__).parent
for who in ('lali','pooli'):
 src=root/who/'fullbody.png'
 raw=src.read_bytes();digest=hashlib.sha256(raw).hexdigest()[:12]
 with Image.open(src) as im:
  figure=im.convert('RGBA');figure.thumbnail((440,670),Image.Resampling.LANCZOS)
  bg=Image.new('RGBA',(512,768),'white');bg.alpha_composite(figure,((512-figure.width)//2,(768-figure.height)//2))
  name=f'jarvis_reference_{who}_{digest}.png';target=comfy/'input'/name
  buf=io.BytesIO();bg.convert('RGB').save(buf,format='PNG');data=buf.getvalue()
  if target.exists() and target.read_bytes()!=data:raise RuntimeError('Immutable input collision')
  if not target.exists():target.write_bytes(data)
 pos=f'High quality clean 2D cartoon full body raccoon {who}, preserve exact clothing, facial markings, silhouette and colors from reference, both feet visible, clean linework, white background'
 neg='cropped, missing feet, missing paws, extra limbs, detached limbs, puppet seams, text, watermark, bad anatomy, inconsistent outfit'
 wf={'1':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':'sd15-pruned-emaonly.safetensors'}},'2':{'class_type':'LoadImage','inputs':{'image':name}},'3':{'class_type':'VAEEncode','inputs':{'pixels':['2',0],'vae':['1',2]}},'4':{'class_type':'CLIPTextEncode','inputs':{'text':pos,'clip':['1',1]}},'5':{'class_type':'CLIPTextEncode','inputs':{'text':neg,'clip':['1',1]}},'6':{'class_type':'KSampler','inputs':{'seed':42,'steps':28,'cfg':6.5,'sampler_name':'euler','scheduler':'normal','denoise':0.28,'model':['1',0],'positive':['4',0],'negative':['5',0],'latent_image':['3',0]}},'7':{'class_type':'VAEDecode','inputs':{'samples':['6',0],'vae':['1',2]}},'8':{'class_type':'SaveImage','inputs':{'filename_prefix':'Jarvis_ReferenceStudy_'+who,'images':['7',0]}}}
 path=out/f'sd15_{who}_reference_api.json';path.write_text(json.dumps(wf,indent=2),encoding='utf-8')
 manifest={'character':who,'source':str(src),'source_sha256':hashlib.sha256(raw).hexdigest(),'input_copy':str(target),'workflow':str(path),'mode':'SD1.5 img2img study; no identity lock','approved_for_publication':False,'animation_completed':False,'reference_source_unchanged':hashlib.sha256(src.read_bytes()).hexdigest()==hashlib.sha256(raw).hexdigest()}
 (out/f'sd15_{who}_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 print(who,'workflow ready','reference preserved',manifest['reference_source_unchanged'])
