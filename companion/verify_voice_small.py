import json,time
from pathlib import Path
from companion_voice import speech_file,transcribe
import companion_settings as s
out=s.ROOT/'reports'/'companion_live';out.mkdir(parents=True,exist_ok=True)
text='Ahoj Davide. Jsem tvůj asistent. Dva plus dva jsou čtyři.'
try:
 voice=speech_file(out/'czech',text);start=time.time();recognized=transcribe(Path(voice['path']).read_bytes(),s.ROOT/'SpeechModels')
 data={'tts':voice,'stt':recognized,'recognition_wall_seconds':round(time.time()-start,2),'scope':'Synthetic voice loopback; physical microphone still requires user interaction'}
except Exception as exc:data={'error':type(exc).__name__,'detail':str(exc)[:500]}
(out/'voice_small.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data,ensure_ascii=True))
