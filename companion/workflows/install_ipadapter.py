from pathlib import Path
import requests,sys,hashlib
root=Path(r'H:\RealJarvis\OptionalPlugins\ComfyUI')
tasks=[
 ('https://huggingface.co/h94/IP-Adapter/resolve/main/models/ip-adapter_sd15.safetensors',root/'models'/'ipadapter'/'ip-adapter_sd15.safetensors',44642768),
 ('https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors',root/'models'/'clip_vision'/'CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors',2528373448)
]
for url,dst,size in tasks:
 dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists() and dst.stat().st_size==size:
  print('READY',dst,flush=True);continue
 temp=dst.with_suffix('.download')
 if temp.exists():temp.unlink()
 print('DOWNLOADING',dst.name,size,flush=True)
 with requests.get(url,stream=True,timeout=(20,120)) as r:
  r.raise_for_status()
  with temp.open('wb') as f:
   for chunk in r.iter_content(1024*1024):
    if chunk:f.write(chunk)
 if temp.stat().st_size!=size:raise RuntimeError(f'incomplete {dst.name}: {temp.stat().st_size} vs {size}')
 temp.replace(dst)
 print('READY',dst,flush=True)
print('MODEL FILES DOWNLOADED; IPADAPTER NODES NOT YET INSTALLED OR TESTED',flush=True)
