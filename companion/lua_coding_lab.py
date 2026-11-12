"""Read-only model patch proposal; actual changes restricted to disposable Lua fixture."""
from pathlib import Path
import json,re,hashlib,subprocess,shutil,tempfile,urllib.request
ROOT=Path(__file__).resolve().parent.parent
F=ROOT/'OpenCodeLuaPilot'
LUA=Path(r'C:\Users\Dawis\AppData\Local\Temp\lua51\lua5.1.exe')
BEG='local function FR_NowNavRepeatsTitle(label,instr)'
END='UIV2.NavRepeatsTitle=FR_NowNavRepeatsTitle'
OLD='           :gsub("%s+"," "):gsub("^%s+",""):gsub("%s+$",""))'
MODEL='qwen3.5:4b-q4_K_M'
REPORT=ROOT/'reports'/'coding_model_pilot.json'
PAT=re.compile(r':gsub\("(?:%p\+\$|\[[%\.!:\?;\[\]]+\]\+\$)",""\)$')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonicalize(line):
 """Only restore fixed indentation and enclosing return parenthesis, never logic."""
 if not isinstance(line,str) or '\r' in line or '\n' in line:return line
 stripped=line.strip()
 if not stripped.startswith(OLD.strip()[:-1]):return line
 if stripped.endswith('","")') and not stripped.endswith('",""))'):
  stripped+=')'
 return ' '*11+stripped

def allowed(line):
 if not isinstance(line,str) or '\n' in line or '\r' in line:return False
 if len(line)>220 or not line.startswith(OLD[:-1]) or not line.endswith('))'):return False
 return bool(PAT.fullmatch(line[len(OLD)-1:-1]))
def native(root):
 src=root/'ForeverRoute_UIv2.lua'
 tst=root/'tests'/'now_card_objectives.lua'
 syn=subprocess.run([str(LUA),'-e',f'assert(loadfile([[{src}]]))'],capture_output=True,timeout=8)
 if syn.returncode:return {'passed':False,'reason':'invalid_lua'}
 out=subprocess.run([str(LUA),str(tst),str(root)],cwd=root,capture_output=True,text=True,errors='replace',timeout=20)
 return {'passed':out.returncode==0 and '72 checks, 0 failures' in out.stdout,'tail':out.stdout[-500:]}
def ask_model(fn,feedback=''):
 instructions=('You fix a Lua 5.1 function. Return ONLY valid JSON with replacement_line. '
 'Make a single added :gsub() call to the existing whitespace normalization line. '
 'Keep all existing calls unchanged; preserve matching of mid-sentence locations and '
 'names within longer words. The new code should strip terminal punctuation from '
 'the normalized instruction so the existing suffix check handles it. '
 'Do NOT change anything else or include commentary.')
 body={'model':MODEL,'stream':False,'think':False,'format':'json','keep_alive':'1m',
 'options':{'num_predict':400,'temperature':0.1},
 'messages':[{'role':'system','content':instructions},
 {'role':'user','content':'Function:\n'+fn+'\nEXISTING LINE:\n'+OLD+
 '\nFailures: K1 period K2 exclamation K3 colon. Negatives K4 and K5 must pass.\n'+feedback}]}
 req=urllib.request.Request('http://127.0.0.1:11434/api/chat',
   data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=75) as res:reply=json.load(res)
 parsed=json.loads(reply.get('message',{}).get('content',''))
 return parsed.get('replacement_line') if isinstance(parsed,dict) else None
def pilot():
 src=F/'ForeverRoute_UIv2.lua';test=F/'tests'/'now_card_objectives.lua'
 before=[digest(src),digest(test)]
 result={'model':MODEL,'source_sha256':before[0],'test_sha256':before[1],
         'baseline':native(F),'model_authored_verified':False,'attempts':[]}
 raw=src.read_text(encoding='utf-8')
 start=raw.index(BEG);end=raw.index(END,start)
 fragment=raw[start:end]
 if fragment.count(OLD)!=1:raise ValueError('unexpected_source')
 feedback=''
 try:
  for i in range(2):
   item={'attempt':i+1,'status':'UNVERIFIED'}
   try:
    line=ask_model(fragment,feedback)
    item['proposal']=line
    line=canonicalize(line)
    item['canonical_proposal']=line
    if not allowed(line):
     item['status']='REJECTED_GUARD'
     feedback='Output did not match one safely allowed gsub line. Try again.'
    else:
     dest=ROOT/'coding_runs';dest.mkdir(exist_ok=True)
     with tempfile.TemporaryDirectory(prefix='sandbox_',dir=dest) as t:
      work=Path(t);(work/'tests').mkdir()
      shutil.copy2(test,work/'tests'/test.name)
      for dep in ('ForeverRoute.lua','ForeverRoute_UIAdapter.lua'):
       shutil.copy2(F/dep,work/dep)
      candidate=raw[:start]+fragment.replace(OLD,line,1)+raw[end:]
      (work/src.name).write_text(candidate,encoding='utf-8')
      sourcecheck=digest(work/'tests'/test.name)
      tested=native(work)
      tests_unchanged=(sourcecheck==digest(work/'tests'/test.name))
      item.update({'test':tested,'tests_unchanged':tests_unchanged})
      item['status']='VERIFIED' if tested['passed'] and tests_unchanged else 'FAILED'
      if item['status']=='VERIFIED':result['model_authored_verified']=True
     feedback='Full Lua tests still failed; try another punctuation-removing pattern.'
   except Exception as exc:
    item.update({'status':'ERROR','error':type(exc).__name__})
    feedback='Reply in JSON with replacement_line only.'
   result['attempts'].append(item)
   if result['model_authored_verified']:break
 finally:
  result['production_source_unchanged']=before==[digest(src),digest(test)]
  REPORT.parent.mkdir(exist_ok=True)
  REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 return result
if __name__=='__main__':
 print(json.dumps(pilot(),ensure_ascii=True)[:4000],flush=True)

