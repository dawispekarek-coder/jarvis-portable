# -*- coding: utf-8 -*-
"""Private, resumable study of 20 distinct animated references, with actual local vision."""
from __future__ import annotations
import base64,hashlib,html,io,json,re,sys,time,urllib.request
from pathlib import Path
import requests,cv2,numpy as np
from PIL import Image,ImageDraw,ImageOps,ImageFont
B=Path(r'H:\RealJarvis\V2Autonomy_20261027\BrainCore')
sys.path.insert(0,str(B))
from companion_store import Store
from companion_settings import STATE
ROOT=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot')
OUT=ROOT/'training'/'learning20'
MEDIA=OUT/'source_clips_private'
SHEETS=OUT/'contact_sheets'
for p in (OUT,MEDIA,SHEETS):p.mkdir(exist_ok=True,parents=True)
SEEDS=[
'16063268655989854717','23496295','18134629107560046461','3132160140743924231',
'1443323334932423689','11578907319517975396','7194682455597828418',
'1352457077149928436','4078337583377800445','16421456271608498676',
'12887522076172795400','8214062922228160874','2118934589185065001',
'3202930018401310243','9674711658669619830','4790070802025163269',
'5758951742620863089','16315837975531020219','16014929987702109227',
'2537612540906666967']
SLUGS=[
'bubu-hug-bubu-hug-dudu-bubu-cry-bubu-dudu-love-bubu-angry',
'bubu-dudu-kiss','dudu-scared-bubu-dudu-kiss-twitter-bubududukiwi',
'bubu-dudu-sleep','bubu-dudu-sleep-good-night',
'bubu-dudu-dudu-dance-bubu-dudu-dance-dudu-cute-dudu-happy',
'bubu-dudu-bubu-dance-woohoo-dance-bubu','dudu-bubu-dance',
'bubu-bubu-dudu-bubu-cry-no-cry-no-crying',
'bubu-dudu-sseeyall-cry','bubu-dudu-sseeyall-cry',
'bubu-dudu-bubu-eat-eating-bubu-eat','bubu-dudu-bubu-eat-rolex-sir-suho-rolex-bubu-angry',
'bubu-eat-bubu-bubu-dudu-bubu-happy-bubu-eating','bubu-dudu-rain','bubu-dudu-rain',
'bubu-dudu-happy-sad-bubu-cry','bubu-dudu-bubu-dudu-bubu-dudu-sleep',
'bubu-dudu-bubududu-kiss-smooch','bubu-dudu-bubu-dudu-dance']
SOURCES=['https://tenor.com/view/'+slug+'-gif-'+ident for slug,ident in zip(SLUGS,SEEDS)]
MANIFEST=OUT/'learning_manifest.json'
if MANIFEST.exists():
 manifest=json.loads(MANIFEST.read_text(encoding='utf8'))
else:manifest={'lessons':[],'rejected':[],'created_at':time.strftime('%Y-%m-%d %H:%M:%S')}
session=requests.Session();session.headers.update({'User-Agent':'Mozilla/5.0 (compatible; JarvisPrivateStudy/1.0)'})
def save():
 MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
def dhash(im):
 a=np.asarray(im.convert('L').resize((9,8),Image.Resampling.LANCZOS))
 return sum((1<<i) for i,v in enumerate((a[:,1:]>a[:,:-1]).flatten()) if v)
def hd(a,b):return (int(a)^int(b)).bit_count()
def find_sources():
 urls=list(SOURCES)
 if len(manifest['lessons'])>=20:return urls
 for query in ['bubu-dudu-gifs','bubu-dudu-love-gifs','bubu-dudu-hug-gifs','bubu-dudu-happy-gifs']:
  try:
   page=session.get('https://tenor.com/search/'+query,timeout=18).text
   found=re.findall(r'href="(/view/[^"]+)"',page)
   for path in found:
    url='https://tenor.com'+html.unescape(path).split('?')[0]
    if re.search(r'-gif-\d+$',url) and url not in urls:urls.append(url)
  except Exception as e:print('SEARCH_WARN',str(e)[:120],flush=True)
 print('CANDIDATES',len(urls),flush=True)
 return urls
def download(url):
 page=session.get(url,timeout=20);page.raise_for_status()
 m=re.search(r'name="twitter:player:stream" content="([^"]+)"',page.text)
 if not m:raise ValueError('no MP4 source in page metadata')
 media_url=html.unescape(m.group(1))
 if not media_url.startswith('https://media.tenor.com/'):
  raise ValueError('unexpected source host')
 res=session.get(media_url,timeout=28)
 res.raise_for_status()
 if len(res.content)>10_000_000 or len(res.content)<5000:raise ValueError('media size outside limits')
 return media_url,res.content
def frames(path):
 cap=cv2.VideoCapture(str(path))
 try:
  if not cap.isOpened():raise ValueError('undecodable MP4')
  n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS)
  if n<6 or fps<1 or n/fps>35:raise ValueError('invalid frames/fps/duration')
  indices=[round((n-1)*f) for f in (0.04,0.27,0.5,0.73,0.96)]
  if len(set(indices))<5:raise ValueError('not five distinct timestamps')
  ims=[]
  for idx in indices:
   cap.set(cv2.CAP_PROP_POS_FRAMES,idx)
   ok,frame=cap.read()
   if not ok:raise ValueError('cannot decode sample')
   ims.append(Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)))
  return ims,[round(i/fps,3) for i in indices],round(n/fps,3),(ims[0].width,ims[0].height)
 finally:cap.release()
def sheet_for(ims,times,ident):
 sheet=Image.new('RGB',(240*5,256),(245,245,245))
 draw=ImageDraw.Draw(sheet)
 for i,(im,t) in enumerate(zip(ims,times)):
  small=ImageOps.contain(im,(232,216))
  x=240*i+(240-small.width)//2;y=(216-small.height)//2
  sheet.paste(small,(x,y))
  draw.text((240*i+9,226),f'frame {i+1}: {t:.2f}s',fill=(10,10,10))
 target=SHEETS/(ident+'.jpg')
 sheet.save(target,quality=82,optimize=True)
 return sheet,target
def vision(sheet,times):
 bio=io.BytesIO();sheet.save(bio,format='JPEG',quality=74)
 prompt=('Na obrázku je přesně PĚT políček JEDNÉ krátké animace v časovém pořadí. '
  'Časy zleva doprava: '+', '.join(map(str,times))+' sekund. '
  'Jsi pozorovatel, nikoli autor děje. Napiš ČESKY 5 krátkých konkrétních bodů: '
  '1) viditelný pohyb a časový vývoj, 2) viditelné výrazy a změna emocí, '
  '3) náběh gesta a reakce druhé postavy, 4) případná rekvizita, pozadí a zda je '
  'skutečně vidět střih, nebo jde spíše o smyčku v jednom záběru, '
  '5) obecná PŮVODNÍ animační lekce použitelná pro jiné mývaly Lali/Pooli. '
  'Co nelze z pěti políček zjistit, výslovně označ jako nejisté. '
  'Nevymýšlej mluvený dialog, záměry ani neviditelné děje. '
  'Nepřepisuj ani nekopíruj cizí postavy, záběry nebo rekvizity. '
  'Max 140 českých slov.')
 payload={'model':'qwen3.5:4b-q4_K_M','messages':[{'role':'user','content':prompt,
  'images':[base64.b64encode(bio.getvalue()).decode()]}],
  'stream':False,'think':False,'options':{'temperature':0.12,'num_predict':400,'num_ctx':4096}}
 req=urllib.request.Request('http://127.0.0.1:11434/api/chat',
  data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=130) as f:
  answer=json.load(f)
 note=answer.get('message',{}).get('content','').strip()
 if len(note)<65:raise ValueError('vision response too short')
 return note
store=Store(STATE)
seen_sha={x['sha256'] for x in manifest['lessons']}
seen_dhash=[int(x['dhash']) for x in manifest['lessons']]
seen_url={x['url'] for x in manifest['lessons']}
for url in find_sources():
 if len(manifest['lessons'])>=20:break
 if url in seen_url:continue
 ident=re.search(r'(\d+)$',url).group(1)
 temp=MEDIA/(ident+'.mp4')
 try:
  media_url,data=download(url)
  sha=hashlib.sha256(data).hexdigest()
  if sha in seen_sha:raise ValueError('exact duplicate')
  temp.write_bytes(data)
  ims,times,duration,size=frames(temp)
  signature=dhash(ims[2])
  if any(hd(signature,x)<=2 for x in seen_dhash):raise ValueError('visually near-duplicate')
  sheet,contact=sheet_for(ims,times,ident)
  note=vision(sheet,times)
  i=len(manifest['lessons'])+1
  record={'index':i,'url':url,'source_mp4_url':media_url,
   'sha256':sha,'dhash':str(signature),'seconds':duration,'size':size,
   'sample_times':times,'contact_sheet':str(contact),'source_clip_private':str(temp),
   'vision_model':'qwen3.5:4b-q4_K_M','vision_notes_cz':note,
   'evidence_scope':'5 sampled frames; no full-video comprehension guaranteed'}
  manifest['lessons'].append(record);seen_sha.add(sha);seen_dhash.append(signature);seen_url.add(url)
  store.remember(f'lali_pooli_reference20_{i:02d}',
   ('Ověřeno 5 dekódovaných snímků originální referenční animace. URL: '+url+
    '; časy '+str(times)+'s; délka '+str(duration)+'s. Pozorování lokálního obrazového modelu: '+note+
    '. Nejde o důkaz střihů mezi vzorky. Pouze inspirace technikou, nekopírovat cizí postavy a záběry.'),
   'vision_reference_sampled_5_frames')
  save()
  print('STUDIED',i,ident,'duration',duration,'note_chars',len(note),flush=True)
 except Exception as exc:
  manifest['rejected'].append({'url':url,'error':str(exc)[:220]})
  save();print('REJECTED',ident,str(exc)[:150],flush=True)
  if temp.is_file() and not any(x.get('source_clip_private')==str(temp) for x in manifest['lessons']):
   temp.unlink()
if len(manifest['lessons'])>=20:
 brief='\n'.join(f"{x['index']}. {x['vision_notes_cz'][:310]}" for x in manifest['lessons'])
 (OUT/'lessons_for_director.txt').write_text(brief,encoding='utf8')
 store.remember('lali_pooli_reference20_index',
  '20 různých ověřených animovaných referencí, vždy 5 skutečně dekódovaných časovaných snímků, '
  'poznámky v paměti lali_pooli_reference20_01 až _20; režijní podklady: '+
  str(OUT/'lessons_for_director.txt')+'. Pozor: analýza modelu je interpretace vzorků, '
  'ne kopie originálních postav.','verified_reference_study')
manifest['finished_at']=time.strftime('%Y-%m-%d %H:%M:%S')
manifest['complete']=len(manifest['lessons'])>=20
save()
print('RESULT',json.dumps({'count':len(manifest['lessons']),
 'rejected':len(manifest['rejected']),'complete':manifest['complete'],
 'manifest':str(MANIFEST)},ensure_ascii=False),flush=True)
if not manifest['complete']:sys.exit(2)
