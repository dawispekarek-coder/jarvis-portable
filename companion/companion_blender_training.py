"""Autonomous ONE STEP of visual Blender learning for Lali: see -> select -> act -> see again.
No pre-scripted character modeling and no publication. Agent chooses next GUI step from image observation.
"""
import json,time,urllib.request
from pathlib import Path
from companion_blender_vision import view
from companion_blender_gui import step
ROOT=Path(r'H:\RealJarvis\OptionalPlugins\JarvisBlender3D')
STATE=ROOT/'Lali_Blender_GUI_training.json'
def model_decision(observation):
 prompt=('Jsi Jarvis, ucis se ovladat OTEVRENY Blender na PC z monitoru. Chces zahajit postavu myvalice Lali. '
 'Rozhodni jednu JEDINOU bezpecnou GUI akci podle aktualniho screenshotu popsaneho nize. '
 'Jestlize je na obrazovce dialog otevreni souboru, akce dismiss_file_dialog. '
 'Jestlize je uprostred Blenderu uvodni obrazovka Splash, akce dismiss_splash. '
 'Jestlize je normalni 3D viewport, ktery obsahuje default Cube a zbytek sceny, akce add_head_sphere. '
 'Jestlize v Outlineru vidis Armature namisto zamyslene UV koule, vrat POSLEDNI MYLNOU akci: undo_last. '
 'Jestlize jiz vidis vytvoreny zvlastni objekt Lali_head_training, akce stop. '
 'Nikdy nemaz obsah, nikdy nespoustej Python konzoli, neposilej nic na Instagram. '
 'Nejde o finalni model. Pouze trenujes prvni skutecnou GUI operaci. '
 'Vrat JSON {"action":"...","reason":"..."} bez jineho textu.\nPozorovani: '+observation)
 schema={'type':'object','properties':{'action':{'type':'string','enum':['dismiss_file_dialog','dismiss_splash','add_head_sphere','undo_last','stop']},'reason':{'type':'string'}},'required':['action','reason']}
 data={'model':'qwen3.5:4b-q4_K_M','messages':[{'role':'user','content':prompt}],'format':schema,'stream':False,'think':False,'options':{'temperature':0,'num_ctx':4096,'num_predict':110}}
 req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(data).encode('utf8'),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=70) as resp:reply=json.load(resp)
 raw=(reply.get('message') or {}).get('content','')
 return json.loads(raw)
def learn_one_step():
 before=view()
 proposal=model_decision(before['observation'])
 action=proposal['action']
 if action=='stop':
  return {'verified':True,'training_step':'stop','observation':before['observation'],'status':'Awaiting actual 3D modeling; no steps performed','screenshot':before['screenshot_file'],'approved':False}
 executed=step(action, name='Lali_head_training' if action=='add_head_sphere' else '')
 if not executed['verified']:raise RuntimeError('GUI change was not visually confirmed: '+str(executed))
 after=view()
 if action=='add_head_sphere':
  check=verify_lali_head()
  if not check.get('sphere_present') or not check.get('name_present'):raise RuntimeError('Wrong Blender primitive: '+str(check))
 previous=json.loads(STATE.read_text(encoding='utf8')) if STATE.is_file() else []
 previous.append({'time':time.strftime('%Y-%m-%dT%H:%M:%S'),'decision':proposal,'before':before['observation'],'action':executed,'after':after['observation']})
 STATE.write_text(json.dumps(previous,ensure_ascii=False,indent=2),encoding='utf8')
 return {'verified':True,'training_step':action,'decision':proposal['reason'],'before':before['observation'],'after':after['observation'],'screenshot':after['screenshot_file'],'total_steps':len(previous),'model_approved':False,'scope':'Verified GUI practice action, not a finished raccoon model'}


def verify_lali_head():
 """Strict visual check of Blender Outliner after adding a head; no mere pixel-change success."""
 import io,base64
 from PIL import Image,ImageGrab
 from companion_blender_vision import locate_blender
 l,t,r,b=locate_blender()
 box=(max(l,r-510),t+48,r-4,min(b,t+510))
 im=ImageGrab.grab(bbox=box,all_screens=True)
 im.thumbnail((1080,900))
 buf=io.BytesIO();im.convert('RGB').save(buf,'JPEG',quality=88)
 image_b64=base64.b64encode(buf.getvalue()).decode()
 prompt=("Na obrazku je PRAVY HORNI PANEL OUTLINER Blenderu. "
 "Cti VYHRADNE skutecna jmena objektu. "
 "Je v seznamu doslova objekt Lali_head_training? "
 "Je tam UV koule, a nebo misto toho Armature? "
 "Neodvozuj stav jen ze zmeny pixelu. Vrat pravdive JSON.")
 schema={"type":"object","properties":{"name_present":{"type":"boolean"},"sphere_present":{"type":"boolean"},"armature_present":{"type":"boolean"},"evidence":{"type":"string"}},"required":["name_present","sphere_present","armature_present","evidence"]}
 body={"model":"qwen3.5:4b-q4_K_M","messages":[{"role":"user","content":prompt,"images":[image_b64]}],"format":schema,"stream":False,"think":False,"options":{"num_predict":120,"temperature":0}}
 req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=70) as response:answer=json.load(response)
 return json.loads((answer.get('message') or {}).get('content','{}'))

