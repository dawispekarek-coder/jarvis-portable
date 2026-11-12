"""Observed Blender GUI and local vision: one window capture plus user-approved reference."""
from pathlib import Path
import base64, ctypes, io, json, os, time, urllib.request
from PIL import Image, ImageGrab
import psutil
BLENDER=Path(r"H:\RealJarvis\OptionalPlugins\Blender4.5LTS\blender-4.5.15-windows-x64\blender.exe")
REPO=Path(r"H:\RealJarvis\OptionalPlugins\JarvisBlender3D")
REF=REPO/"References"/"04_Lali_otocka.jpg"
def locate_blender():
 user32=ctypes.windll.user32
 # Activate only the verified local Blender process before observing its GUI.
 from pywinauto import Desktop
 for w in Desktop(backend="win32").windows():
  try:
   if os.path.normcase(psutil.Process(w.process_id()).exe())==os.path.normcase(str(BLENDER)) and "Blender" in w.window_text():
    w.set_focus()
    time.sleep(.25)
    break
  except Exception:
   continue
 h=user32.GetForegroundWindow()
 if not h: raise RuntimeError("No active window")
 pid=ctypes.c_ulong(0);user32.GetWindowThreadProcessId(h,ctypes.byref(pid))
 p=psutil.Process(pid.value)
 if os.path.normcase(p.exe())!=os.path.normcase(str(BLENDER)):raise RuntimeError("Blender is not active foreground window")
 class RECT(ctypes.Structure):_fields_=[("left",ctypes.c_long),("top",ctypes.c_long),("right",ctypes.c_long),("bottom",ctypes.c_long)]
 r=RECT();user32.GetWindowRect(h,ctypes.byref(r))
 if r.right-r.left<400 or r.bottom-r.top<300:raise RuntimeError("Blender viewport too small")
 return (r.left,r.top,r.right,r.bottom)
def snap():
 b=locate_blender()
 im=ImageGrab.grab(bbox=b,all_screens=True)
 im.thumbnail((1080,720))
 out=REPO/"observations";out.mkdir(exist_ok=True)
 file=out/("blender_"+str(int(time.time()))+".jpg")
 im.convert("RGB").save(file,quality=75)
 return file
def view():
 screenshot=snap()
 with Image.open(screenshot) as im:
  bio=io.BytesIO();im.save(bio,format="JPEG",quality=65);screen=base64.b64encode(bio.getvalue()).decode()
 if not REF.is_file():raise RuntimeError("approved raccoon reference unavailable")
 reference=base64.b64encode(REF.read_bytes()).decode()
 query=("Prvni obrazek je PRAVE AKTIVNI okno Blenderu. Druhy obrazek je vizualni predloha myvalice Lali. "
        "Strucne cesky a fakticky rekni, co je skutecne videt v Blenderu (dialog? krychle? model?);"
        "jaky JEDEN bezpecny dalsi krok uzivatele v GUI doporucujes. "
        "Nerikej, ze model odpovida predloze, pokud je viditelne vyrazne jiny. "
        "Nerikej, ze akce probehla. Bez titulkoveho vytvareni. Max 80 slov.")
 body={"model":"qwen3.5:4b-q4_K_M","messages":[{"role":"user","content":query,"images":[screen,reference]}],"stream":False,"think":False,"options":{"num_predict":160,"temperature":0.1,"num_ctx":4096}}
 req=urllib.request.Request("http://127.0.0.1:11434/api/chat",data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=85) as response:result=json.load(response)
 txt=(result.get("message") or {}).get("content") or ""
 if not txt.strip():raise RuntimeError("vision_model_returned_no_text")
 return {"verified":True,"screen_observed":True,"reference_used":True,"observation":txt[:1300],"screenshot_file":str(screenshot),"character_model_approved":False}
if __name__=="__main__":print(json.dumps(view(),ensure_ascii=False))
