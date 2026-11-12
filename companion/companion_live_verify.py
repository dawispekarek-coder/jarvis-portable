import json,time,traceback
from pathlib import Path
import companion_settings as s
out=s.ROOT/'reports'/'companion_live';out.mkdir(parents=True,exist_ok=True)
r={}
try:
 from companion_browser import Browser
 b=Browser(s.ROOT/'CompanionBrowserSmoke',out)
 page=b.open('https://example.com')
 r['browser']={'verified':page['verified'],'title':page['title'],'url':page['url'],'elements':len(page['elements'])}
 b.close()
except Exception as e:r['browser']={'error':type(e).__name__,'detail':str(e)[:350]}
try:
 from playwright.sync_api import sync_playwright
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='msedge',headless=True)
  page=browser.new_page(viewport={'width':1366,'height':900});errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:7430',wait_until='networkidle',timeout=30000)
  page.wait_for_timeout(1500)
  r['ui']={'title':page.title(),'text_chars':len(page.locator('body').inner_text()),'errors':errors,'companion_buttons':page.get_by_role('button',name='Ukoly',exact=False).count()}
  page.screenshot(path=str(out/'companion_ui.png'),full_page=True)
  browser.close()
except Exception as e:r['ui']={'error':type(e).__name__,'detail':str(e)[:400]}
try:
 from companion_voice import speech_file,transcribe
 voice=speech_file(out,'Ahoj Davide, tady Jarvis. Dva plus dva jsou ctyri.')
 r['tts']=voice
 text=transcribe(Path(voice['path']).read_bytes(),s.ROOT/'SpeechModels')
 r['stt_loopback']=text
except Exception as e:r['voice_error']={'error':type(e).__name__,'detail':str(e)[:400]}
(out/'results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(r,ensure_ascii=True),flush=True)
