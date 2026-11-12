"""Digital13 output and CPU-bounded local Czech speech recognition."""
from __future__ import annotations
import io,wave,json,urllib.request,importlib.util,threading
from pathlib import Path

def validate_audio(raw,content_type):
 if len(raw)<44 or len(raw)>20000000 or 'audio' not in content_type:raise ValueError('invalid_audio_response')
 try:
  with wave.open(io.BytesIO(raw),'rb') as f:
   if f.getnframes()<1 or f.getnchannels() not in (1,2):raise ValueError('empty_audio')
   return {'frames':f.getnframes(),'sample_rate':f.getframerate(),'seconds':f.getnframes()/f.getframerate()}
 except (wave.Error,EOFError) as exc:raise ValueError('invalid_wav') from exc

def tts_status():
 try:
  with urllib.request.urlopen('http://127.0.0.1:7341/api/tts/status',timeout=2) as r:data=json.load(r)
  return data
 except (OSError,ValueError):return {'available':False,'provider':'unavailable','voice':'M3-Digital13'}

def synthesize(text):
 if not isinstance(text,str) or not 1<=len(text.strip())<=3500:raise ValueError('invalid_speech_text')
 req=urllib.request.Request('http://127.0.0.1:7341/api/tts',data=json.dumps({'text':text}).encode('utf-8'),headers={'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=65) as response:raw=response.read(20000001);kind=response.headers.get('Content-Type','')
 validate_audio(raw,kind);return raw

def speech_file(root,text):
 raw=synthesize(text);root=Path(root);root.mkdir(parents=True,exist_ok=True);path=root/'voice.wav';path.write_bytes(raw)
 return {'path':str(path),'audio':validate_audio(path.read_bytes(),'audio/wav'),'verified':True,'scope':'Audio file generated; browser playback has separate confirmation'}

_MODEL=None;_LOCK=threading.Lock()
def stt_status(root):
 installed=bool(importlib.util.find_spec('faster_whisper'));downloaded=any(Path(root).glob('models--Systran--faster-whisper-small/**/model.bin'))
 return {'installed':installed,'model_cached':downloaded,'available':installed,'model':'small','language':'cs','device':'cpu','microphone_permission_required':True,'first_run_download':not downloaded}

def transcribe(raw,root):
 global _MODEL
 if not 64<=len(raw)<=15000000:raise ValueError('invalid_audio_size')
 if not _LOCK.acquire(blocking=False):raise RuntimeError('speech_recognition_busy')
 try:
  if _MODEL is None:
   from faster_whisper import WhisperModel
   _MODEL=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=2,num_workers=1,download_root=str(root))
  segments,info=_MODEL.transcribe(io.BytesIO(raw),language='cs',beam_size=1,vad_filter=True,condition_on_previous_text=False)
  if info.duration>90:raise ValueError('audio_exceeds_90_seconds')
  text=' '.join(s.text.strip() for s in segments).strip()
  if not text:raise ValueError('no_speech_recognized')
  return {'text':text[:6000],'language':'cs','seconds':info.duration,'verified':True,'scope':'Local transcription, not verified user intent'}
 finally:_LOCK.release()
