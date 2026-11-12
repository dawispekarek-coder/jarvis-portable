# -*- coding: utf-8 -*-
"""Bounded original Godot homecoming DRAFT; technical success != creative approval."""
from __future__ import annotations
from pathlib import Path
import base64,io,json,math,subprocess,time,urllib.request,wave
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageOps
ROOT=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot')
STUDY=ROOT/'training'/'homecoming'
GODOT=Path(r'H:\RealJarvis\OptionalPlugins\Godot4.7.2\Godot_v4.7.2-stable_win64.exe')
FFMPEG=Path(r'H:\RealJarvis\OptionalPlugins\JarvisVideo\.venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe')
SCENE='res://training/homecoming/Stage4_Homecoming.tscn'
def audio(path):
 rate=22050
 samples=np.zeros(int(14*rate),dtype=np.float64)
 rng=np.random.default_rng(2801)
 def add(t,duration,freq,vol=.16,kind='sine'):
  n=int(duration*rate);i=np.arange(n)/rate
  env=np.sin(np.pi*np.clip(i/duration,0,1))**2
  if kind=='noise':tone=rng.standard_normal(n)*env
  elif kind=='chirp':tone=np.sin(2*np.pi*(freq*i+110*i*i))*env
  else:tone=np.sin(2*np.pi*freq*i)*env
  start=int(t*rate);end=min(len(samples),start+n)
  if end>start:samples[start:end]+=tone[:end-start]*vol
 # A few original footsteps, creaky door, happy non-verbal sparkle, soft hug.
 for x in (2.65,3.08,3.5,4.0,4.45,7.9,8.23,8.56,8.89,9.2):
  add(x,.12,80,.06,'noise')
 add(2.25,.55,120,.07,'chirp')
 add(5.2,.26,540,.09,'chirp')
 add(5.55,.22,720,.07,'chirp')
 add(9.8,.22,260,.08,'sine')
 for x,f in ((11.1,523),(11.38,659),(11.68,784),(12.1,1046)):
  add(x,.32,f,.07,'sine')
 peak=max(1,float(np.max(np.abs(samples))))
 pcm=np.int16(np.clip(samples/peak*.66,-1,1)*32767)
 with wave.open(str(path),'wb') as f:
  f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes(pcm.tobytes())
def sample_and_qa(mp4,dir):
 cap=cv2.VideoCapture(str(mp4))
 if not cap.isOpened():raise RuntimeError('Video not decodable')
 try:
  width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
  fps=cap.get(cv2.CAP_PROP_FPS);frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
  shots=[1.4,3.7,6.4,9.4,12.3]
  pics=[]
  for x in shots:
   cap.set(cv2.CAP_PROP_POS_MSEC,x*1000)
   ok,f=cap.read()
   if not ok:raise RuntimeError('Cannot decode shot '+str(x))
   pics.append(Image.fromarray(cv2.cvtColor(f,cv2.COLOR_BGR2RGB)))
  cuts=[]
  for t in (2.7,5.15,7.75,11.1):
   cap.set(cv2.CAP_PROP_POS_FRAMES,int((t-.08)*fps))
   ok1,a=cap.read()
   cap.set(cv2.CAP_PROP_POS_FRAMES,int((t+.08)*fps))
   ok2,b=cap.read()
   if ok1 and ok2:
    difference=float(np.abs(a.astype(np.int16)-b.astype(np.int16)).mean())/255.0
    cuts.append({'at':t,'difference':round(difference,3),'visible_change':difference>.045})
 finally:cap.release()
 board=Image.new('RGB',(5*250,480),'#f2f0ed')
 d=ImageDraw.Draw(board)
 for i,(img,x) in enumerate(zip(pics,shots)):
  im=ImageOps.contain(img,(245,430))
  board.paste(im,(i*250+(250-im.width)//2,10))
  d.text((i*250+6,446),f'Shot {i+1} at {x}s',fill='black')
 contact=dir/'homecoming_five_shots.jpg';board.save(contact,quality=83)
 buf=io.BytesIO();board.save(buf,format='JPEG',quality=75)
 prompt=('Pět skutečných políček z našeho NOVÉHO původního 2D videa Lali (růžová mašle) a Pooli (modrá kšiltovka). '
 'Česky kriticky popiš, co OPRAVDU vidíš: Je srozumitelné, že Pooli přichází domů z práce, Lali ho vítá, a oba se objímají? '
 'Jsou pózy přirozené? Je Pooliho tvář konzistentní bez make-upu a řas? '
 'Co je nekvalitní? Buď přísný, nevydávej storyboard za finální animaci. '
 'Přiznej, co z pěti políček nelze určit. Max 140 slov.')
 body={'model':'qwen3.5:4b-q4_K_M','messages':[{'role':'user','content':prompt,
  'images':[base64.b64encode(buf.getvalue()).decode()]}],'stream':False,'think':False,
  'options':{'num_predict':370,'num_ctx':4096,'temperature':0.1}}
 try:
  req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(body,ensure_ascii=False).encode(),
    headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=105) as r:
   vision=json.load(r).get('message',{}).get('content','')
 except Exception as exc:vision='VISION_QA_UNAVAILABLE: '+type(exc).__name__
 return {'frames':frames,'fps':fps,'resolution':[width,height],
  'duration_seconds':round(frames/fps,3) if fps else None,
  'shot_centers':shots,'cuts':cuts,'contact_sheet':str(contact),
  'local_vision_critique':vision,
  'technical_pass':(width==1080 and height==1920 and 23.5<fps<24.5 and 333<=frames<=338 and len(cuts)==4),
  'creative_approved':False,
  'creative_rejection_reasons':['5 key poses/frames cannot establish smooth acting or character identity',
    'Faces and expressions are mostly static, no approved multi-angle rig',
    'Native resolution must be verified from decoded source, not only the MP4 metadata',
    'Procedural environment and prop are study-grade, not studio-quality',
    'Independent human visual review of full clip is still required']}
def render_homecoming():
 for path in (GODOT,FFMPEG,ROOT/'training'/'homecoming'/'Stage4_Homecoming.tscn'):
  if not path.is_file():raise RuntimeError('Missing rendering dependency '+str(path))
 stamp=time.strftime('%Y%m%d_%H%M%S')
 output_dir=STUDY/('run_'+stamp)
 output_dir.mkdir(parents=True,exist_ok=True)
 avi=output_dir/'godot_raw.avi'
 wav=output_dir/'original_sound.wav'
 dest=Path.home()/'Desktop'/'Jarvis_Reels'/('Lali_Pooli_Homecoming_DRAFT_NOT_APPROVED_'+stamp+'.mp4')
 dest.parent.mkdir(parents=True,exist_ok=True)
 audio(wav)
 command=[str(GODOT),'--path',str(ROOT),'--write-movie',str(avi),
  '--fixed-fps','24','--quit-after','336','--resolution','1080x1920',SCENE]
 run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
  text=True,errors='replace',timeout=150)
 if run.returncode or 'Done recording movie at path:' not in run.stdout or not avi.is_file():
  raise RuntimeError('Godot export failed: '+run.stdout[-1000:])
 cap_native=cv2.VideoCapture(str(avi))
 native_size=(int(cap_native.get(cv2.CAP_PROP_FRAME_WIDTH)),int(cap_native.get(cv2.CAP_PROP_FRAME_HEIGHT)))
 cap_native.release()
 if native_size!=(1080,1920):raise RuntimeError('Godot native render not 1080x1920: '+str(native_size))
 encode=subprocess.run([str(FFMPEG),'-hide_banner','-loglevel','error','-y',
  '-i',str(avi),'-i',str(wav),'-map','0:v:0','-map','1:a:0',
  '-vf','fps=24,format=yuv420p',
  '-c:v','libx264','-preset','veryfast','-crf','21',
  '-c:a','aac','-b:a','128k','-t','14','-movflags','+faststart',str(dest)],
  stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',timeout=150)
 if encode.returncode or not dest.is_file() or dest.stat().st_size<50000:
  raise RuntimeError('ffmpeg failed: '+encode.stdout[-700:])
 qa=sample_and_qa(dest,output_dir)
 report={'preview_file':str(dest),'creative_quality_approved':False,'published':False,
  'stage':'DRAFT_NOT_APPROVED','story':'Pooli comes home from work; Lali greets and hugs him',
  'original_assets_only':True,'original_sound':True,'godot_scene':SCENE,
  'qa':qa,'bytes':dest.stat().st_size}
 (output_dir/'render_qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 print('HOME_RENDER',json.dumps({'mp4':str(dest),'technical_pass':qa['technical_pass'],
  'cuts':qa['cuts'],'creative_approved':False},ensure_ascii=False),flush=True)
 return report
if __name__=='__main__':render_homecoming()
