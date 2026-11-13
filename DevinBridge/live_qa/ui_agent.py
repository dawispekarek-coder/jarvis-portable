"""Read-only WoW Forever UI smoke, via Battle.net; no gameplay or credentials."""
import ctypes, time, json, subprocess
from ctypes import wintypes
from pathlib import Path
import pyautogui as pg
import pygetwindow as gw
from PIL import Image,ImageChops,ImageStat
from qa_manager import WOW,wow_running,report
ROOT=Path(__file__).resolve().parent
T=ROOT/'ui_templates'
POPUP_SEEN=False
pg.FAILSAFE=True
RECT={'play':(547,769,650,805),'account':(488,723,701,752),
 'wow_favorite':(582,291,624,335),'char_name':(1570,249,1775,286),
 'enter_world':(871,981,1036,1023),'char_back':(36,1031,190,1065),
 'login_quit':(1720,991,1867,1034),'world_hotbar':(678,710,1163,824),
 'block_ignore':(947,192,1075,225),
 'world_portrait':(298,573,570,653),'world_minimap_frame':(1712,44,1882,245)}
LIM={'play':12,'account':12,'wow_favorite':15,'char_name':13,
 'enter_world':18,'char_back':18,'login_quit':14,
 'world_hotbar':39,'block_ignore':14,
 'world_portrait':52,'world_minimap_frame':48}
def difference(name,shot=None):
 shot=shot or pg.screenshot()
 ref=Image.open(T/(name+'.png')).convert('RGB')
 crop=shot.crop(RECT[name]).convert('RGB')
 if crop.size!=ref.size:return 255
 return sum(ImageStat.Stat(ImageChops.difference(ref,crop)).mean)/3
def match(name):return difference(name)<=LIM[name]
def locked():
 u=ctypes.windll.user32;h=u.OpenInputDesktop(0,False,0x100)
 if not h:return True
 u.CloseDesktop(h);return False
class LASTINPUTINFO(ctypes.Structure):
 _fields_=[('cbSize',wintypes.UINT),('dwTime',wintypes.DWORD)]
def last_input_tick():
 v=LASTINPUTINFO();v.cbSize=ctypes.sizeof(v)
 if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(v)):
  return None
 return v.dwTime
def idle():
 v=LASTINPUTINFO();v.cbSize=ctypes.sizeof(v)
 if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(v)):return 0
 return ((ctypes.windll.kernel32.GetTickCount()-v.dwTime)&0xffffffff)/1000
def stop():return (ROOT/'LIVEQA_STOP.flag').exists()
def wait(predicate,seconds):
 end=time.monotonic()+seconds
 baseline=last_input_tick()
 while time.monotonic()<end:
  if stop():raise RuntimeError('Owner LIVEQA_STOP.flag')
  if locked():raise RuntimeError('Desktop locked during QA')
  # During a wait phase the agent never sends input. Unexpected input is
  # therefore treated as the owner taking over the PC; stop immediately.
  current=last_input_tick()
  if baseline is not None and current is not None and current!=baseline:
   raise RuntimeError('Unexpected user input during QA; stop automation')
  if predicate():return True
  time.sleep(2)
 return False
def world():
 w=gw.getActiveWindow()
 if not w or w.title!='World of Warcraft':return False
 if match('char_name') or match('login_quit'):return False
 return match('world_hotbar') or (match('world_portrait') and match('world_minimap_frame'))
def command(text):
 if text not in ('/reload','/logout'):raise ValueError('Only diagnostic commands permitted')
 if not world():raise RuntimeError('Unknown game UI before slash command')
 import pyperclip
 original=pyperclip.paste()
 try:
  pg.click(130,1012);pg.hotkey('ctrl','a')
  pyperclip.copy(text);pg.hotkey('ctrl','v');time.sleep(.35);pg.press('enter')
 finally:pyperclip.copy(original)
def launch():
 if wow_running():raise RuntimeError('Wow already active; do not interrupt owner')
 exe=Path(r'H:\Battle.net\Battle.net.exe')
 if not exe.is_file():raise RuntimeError('Battle.net missing')
 wins=[x for x in gw.getAllWindows() if x.title=='Battle.net']
 if not wins:
  subprocess.Popen([str(exe)],cwd=str(exe.parent))
  if not wait(lambda:bool([x for x in gw.getAllWindows() if x.title=='Battle.net']),60):
   raise RuntimeError('Battle.net launch failed')
  wins=[x for x in gw.getAllWindows() if x.title=='Battle.net']
 w=wins[0]
 if w.isMinimized:w.restore()
 try:w.activate()
 except Exception:pass
 if not wait(lambda:match('wow_favorite') and match('account'),25):
  raise RuntimeError('Battle.net game/account not recognized')
 if not match('play'):raise RuntimeError('Battle.net Play unavailable')
 pg.click(597,788)
 if not wait(wow_running,65):raise RuntimeError('WoW did not start from Battle.net')
def enter():
 global POPUP_SEEN
 if not wait(lambda:match('char_name') and match('enter_world') and
             bool(gw.getActiveWindow()) and
             gw.getActiveWindow().title=='World of Warcraft',150):
  raise RuntimeError('Character selection differs; credentials/realm/character gate')
 pg.click(952,1003)
 if not wait(world,140):raise RuntimeError('Game world did not load')
 if match('block_ignore'):
  POPUP_SEEN=True
  pg.click(1015,208);time.sleep(.4)  # ignore taint warning; NEVER disable addon
 if not world():raise RuntimeError('Unknown game UI after ignoring warning')
def latest():
 root=WOW/'WTF'/'Account'
 if not root.is_dir():return None
 matches=list(root.glob('*/SavedVariables/ForeverRouteLiveQA.lua'))
 return max(matches,key=lambda x:x.stat().st_mtime) if matches else None
def reload_result():
 existing=latest();before=existing.stat().st_mtime if existing else 0
 started=time.time()
 command('/reload')
 if not wait(world,110):raise RuntimeError('Game did not return from reload')
 global POPUP_SEEN
 if match('block_ignore'):
  POPUP_SEEN=True
  pg.click(1015,208)
 if not wait(lambda:bool(latest() and latest().stat().st_mtime>max(before,started-2)),85):
  raise RuntimeError('No new ForeverRoute LiveQA SavedVariables after reload')
 data=report()
 if data.get('state')!='LIVE_RESULT_RECORDED' or data.get('result') not in ('PASS','WARN','FAIL'):
  raise RuntimeError('LiveQA result missing/incomplete')
 return data
def exit_game():
 global POPUP_SEEN
 if match('block_ignore'):
  POPUP_SEEN=True
  pg.click(1015,208);time.sleep(.5)
 if not world():raise RuntimeError('Unknown game UI; cannot safely logout')
 command('/logout')
 if not wait(lambda:match('char_name') and match('enter_world'),90):
  raise RuntimeError('Logout did not return to known character screen')
 if not match('char_back'):raise RuntimeError('Character Back control not recognized')
 pg.click(100,1047)
 if not wait(lambda:match('login_quit'),30):
  raise RuntimeError('Quit control not recognized')
 pg.click(1795,1008)
 if not wait(lambda:not wow_running(),45):
  raise RuntimeError('WoW did not quit, no forced termination')
def preflight():
 if stop():raise RuntimeError('Owner stop flag')
 if wow_running():raise RuntimeError('WoW already running')
 if locked():raise RuntimeError('Desktop locked')
 if idle()<600:raise RuntimeError('PC has not been idle 10 minutes')
 if tuple(pg.size())!=(1920,1080):raise RuntimeError('Screen resolution changed')
 if len([x for x in gw.getAllWindows() if x.title=='World of Warcraft']):
  raise RuntimeError('WoW window already present')
 for name in RECT:
  if not (T/(name+'.png')).is_file():raise RuntimeError('Visual template missing: '+name)
def run():
 preflight()
 state={'state':'STARTED','at':time.time()}
 try:
  launch();state['state']='GAME_LAUNCHED'
  enter();state['state']='CHARACTER_LOGGED_IN'
  state['qa']=reload_result();state['protected_popup_seen']=POPUP_SEEN;state['state']='RESULT_COLLECTED'
  exit_game();state['protected_popup_seen']=POPUP_SEEN;state['state']='COMPLETE'
 except Exception as e:
  state['reason']=str(e);state['state']='ATTENTION'
  raise
 finally:
  state['protected_popup_seen']=POPUP_SEEN
  state['ended_at']=time.time()
  (ROOT/'ui_last_run.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
 return state
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--selftest',action='store_true')
 args=a.parse_args()
 if args.selftest:
  print(json.dumps({'game_running':wow_running(),'desktop_locked':locked(),
   'user_idle_s':round(idle()),'screen_ok':tuple(pg.size())==(1920,1080),
   'visual_templates':{x:round(difference(x),2) for x in RECT}},indent=2))
 else:
  print(json.dumps(run(),indent=2))
