"""Own disposable Win32 fixture: no interaction with the user's documents."""
import sys,time,json,ctypes,subprocess
from pathlib import Path
import companion_settings as s
OUT=s.ROOT/'reports'/'companion_live';OUT.mkdir(parents=True,exist_ok=True)
TITLE='JARVIS UIA Verification'
if '--fixture' in sys.argv:
 from ctypes import wintypes as w
 u=ctypes.windll.user32;k=ctypes.windll.kernel32
 LRESULT=ctypes.c_longlong;WNDPROC=ctypes.WINFUNCTYPE(LRESULT,w.HWND,w.UINT,w.WPARAM,w.LPARAM)
 u.DefWindowProcW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];u.DefWindowProcW.restype=LRESULT
 u.CreateWindowExW.argtypes=[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.HWND,w.HMENU,w.HINSTANCE,ctypes.c_void_p];u.CreateWindowExW.restype=w.HWND
 k.GetModuleHandleW.restype=w.HINSTANCE
 u.SetWindowTextW.argtypes=[w.HWND,w.LPCWSTR]
 u.ShowWindow.argtypes=[w.HWND,ctypes.c_int]
 edit=None
 def wndproc(hwnd,msg,wp,lp):
  if msg==0x0111 and (int(wp)&65535)==1002:u.SetWindowTextW(edit,'Activated');return 0
  if msg==0x0002:u.PostQuitMessage(0);return 0
  return u.DefWindowProcW(hwnd,msg,wp,lp)
 proc=WNDPROC(wndproc)
 class WC(ctypes.Structure):_fields_=[('style',w.UINT),('lpfnWndProc',WNDPROC),('cbClsExtra',ctypes.c_int),('cbWndExtra',ctypes.c_int),('hInstance',w.HINSTANCE),('hIcon',w.HICON),('hCursor',w.HANDLE),('hbrBackground',w.HBRUSH),('lpszMenuName',w.LPCWSTR),('lpszClassName',w.LPCWSTR)]
 instance=k.GetModuleHandleW(None);wc=WC();wc.lpfnWndProc=proc;wc.hInstance=instance;wc.lpszClassName='JarvisVerificationClass';u.RegisterClassW(ctypes.byref(wc))
 hwnd=u.CreateWindowExW(0,wc.lpszClassName,TITLE,0x10CF0000,180,180,450,180,None,None,instance,None)
 edit=u.CreateWindowExW(0x200,'EDIT','',0x50010080,20,25,380,28,hwnd,1001,instance,None)
 u.CreateWindowExW(0,'BUTTON','Activate test',0x50010000,20,70,180,30,hwnd,1002,instance,None)
 u.ShowWindow(hwnd,5);u.UpdateWindow(hwnd)
 msg=w.MSG()
 while u.GetMessageW(ctypes.byref(msg),None,0,0)>0:u.TranslateMessage(ctypes.byref(msg));u.DispatchMessageW(ctypes.byref(msg))
 sys.exit(0)
import psutil
for process in psutil.process_iter(['pid','cmdline']):
 try:
  command=process.info.get('cmdline') or []
  if '--fixture' in command and str(Path(__file__).resolve()) in command:process.terminate();process.wait(timeout=3)
 except psutil.Error:pass
fixture_log=(OUT/'desktop_fixture.log').open('wb')
fixture=subprocess.Popen([sys._base_executable,str(Path(__file__).resolve()),'--fixture'],stdout=fixture_log,stderr=fixture_log)
try:
 from pywinauto import Desktop
 from companion_desktop import DesktopAdapter
 deadline=time.time()+12;window=None
 while time.time()<deadline:
  try:
   found=[w for w in Desktop(backend='uia').windows() if w.element_info.name==TITLE and w.element_info.process_id==fixture.pid]
   if found:window=found[0];break
  except Exception:pass
  time.sleep(.1)
 if window is None:
  fixture_log.flush();raise RuntimeError('fixture_window_missing: '+(OUT/'desktop_fixture.log').read_text(errors='replace')[-500:])
 window.set_focus();adapter=DesktopAdapter(OUT/'desktop');snapshot=adapter.observe(TITLE)
 field=next(e for e in snapshot['elements'] if e['role']=='Edit')
 result=adapter.fill(field['ref'],'Ahoj Davide.',snapshot['document_id'],snapshot['state_hash'])
 button=next(e for e in result['elements'] if e['name']=='Activate test')
 clicked=adapter.click(button['ref'],result['document_id'],result['state_hash'])
 data={'observed':snapshot['verified'],'controls':len(snapshot['elements']),'fill_verified':result['field_value_verified'],'invoke_verified':clicked['verified'],'fixture_only':True}
except Exception as exc:
 import traceback
 data={'error':type(exc).__name__,'detail':str(exc),'trace':traceback.format_exc(),'fixture_only':True}
finally:
 if fixture.poll() is None:fixture.terminate();fixture.wait(timeout=5)
 fixture_log.close()
(OUT/'desktop_live.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data,ensure_ascii=True))
