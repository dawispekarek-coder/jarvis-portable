"""Post-hoc Lua edge cases the model was not shown, disposable copy only."""
import json,subprocess,tempfile,shutil
from pathlib import Path
import lua_coding_lab as lab
INS='''-- Additional unseen-to-model punctuation cases
check(UIV2.NavRepeatsTitle("Thork","Talk to Thork?"),"HOLD1: question mark")
check(UIV2.NavRepeatsTitle("Bloodhoof Village","Reach Bloodhoof Village;"),"HOLD2: semicolon")
check(UIV2.NavRepeatsTitle("Thork","Talk to Thork..."),"HOLD3: repeated period")
check(not UIV2.NavRepeatsTitle("Thork","Talk to Thorktower?"),"HOLD4: no partial-name match")
'''
def run():
 report=json.loads(lab.REPORT.read_text(encoding='utf-8'))
 attempt=next(x for x in report['attempts'] if x['status']=='VERIFIED')
 patch=attempt['canonical_proposal']
 original=lab.F/'ForeverRoute_UIv2.lua'
 baseline=[lab.digest(original),lab.digest(lab.F/'tests'/'now_card_objectives.lua')]
 with tempfile.TemporaryDirectory(prefix='holdout_',dir=lab.ROOT/'coding_runs') as d:
  temp=Path(d);(temp/'tests').mkdir()
  for name in ('ForeverRoute.lua','ForeverRoute_UIAdapter.lua'):
   shutil.copy2(lab.F/name,temp/name)
  raw=original.read_text(encoding='utf-8')
  i=raw.index(lab.BEG);j=raw.index(lab.END,i)
  frag=raw[i:j]
  if frag.count(lab.OLD)!=1:raise ValueError('source mismatch')
  (temp/original.name).write_text(raw[:i]+frag.replace(lab.OLD,patch)+raw[j:],encoding='utf-8')
  test=(lab.F/'tests'/'now_card_objectives.lua').read_text(encoding='utf-8')
  marker='-- --------------------------------------------------------------- report'
  if test.count(marker)!=1:raise ValueError('test insertion point missing')
  (temp/'tests'/'now_card_objectives.lua').write_text(test.replace(marker,INS+marker),encoding='utf-8')
  out=subprocess.run([str(lab.LUA),str(temp/'tests'/'now_card_objectives.lua'),str(temp)],cwd=temp,capture_output=True,text=True,timeout=20,errors='replace')
  verdict={'returncode':out.returncode,'last_lines':out.stdout.strip().splitlines()[-10:],
    'model_did_not_see_holdout':True,
    'original_unchanged':baseline==[lab.digest(original),lab.digest(lab.F/'tests'/'now_card_objectives.lua')]}
 (lab.ROOT/'reports'/'coding_holdout_pilot.json').write_text(json.dumps(verdict,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(verdict,ensure_ascii=False),flush=True)
 return verdict
if __name__=='__main__':run()