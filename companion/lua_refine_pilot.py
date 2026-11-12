"""Model feedback loop on held-out Lua punctuation cases (isolated only)."""
import json,shutil,tempfile,subprocess
from pathlib import Path
import lua_coding_lab as lab
from lua_holdout_eval import INS
REPORT=lab.ROOT/'reports'/'coding_refinement_pilot.json'
def eval_patch(line):
 source=lab.F/'ForeverRoute_UIv2.lua'
 src=source.read_text(encoding='utf-8')
 a=src.index(lab.BEG);b=src.index(lab.END,a)
 assert src[a:b].count(lab.OLD)==1 and lab.allowed(line)
 with tempfile.TemporaryDirectory(prefix='refine_',dir=lab.ROOT/'coding_runs') as t:
  root=Path(t);(root/'tests').mkdir()
  for name in ('ForeverRoute.lua','ForeverRoute_UIAdapter.lua'):
   shutil.copy2(lab.F/name,root/name)
  (root/source.name).write_text(src[:a]+src[a:b].replace(lab.OLD,line)+src[b:],encoding='utf-8')
  test=(lab.F/'tests'/'now_card_objectives.lua').read_text(encoding='utf-8')
  marker='-- --------------------------------------------------------------- report'
  (root/'tests'/'now_card_objectives.lua').write_text(test.replace(marker,INS+marker),encoding='utf-8')
  out=subprocess.run([str(lab.LUA),str(root/'tests'/'now_card_objectives.lua'),str(root)],
      cwd=root,capture_output=True,text=True,errors='replace',timeout=19)
  result={'passed':out.returncode==0 and '76 checks, 0 failures' in out.stdout,
          'tail':out.stdout[-700:]}
 return result
def run():
 src=lab.F/'ForeverRoute_UIv2.lua';tst=lab.F/'tests'/'now_card_objectives.lua'
 before=[lab.digest(src),lab.digest(tst)]
 raw=src.read_text(encoding='utf-8')
 fn=raw[raw.index(lab.BEG):raw.index(lab.END)]
 prior=json.loads(lab.REPORT.read_text(encoding='utf-8'))
 prior_code=next(x['proposal'] for x in prior['attempts'] if x['status']=='VERIFIED')
 feedback=('Previous proposed line was '+str(prior_code)+  '. Additional independent Lua tests failed: label Thork at end of "Talk to Thork?" '
  'and Bloodhoof Village at end of "Reach Bloodhoof Village;" should be duplicates. '
  'Do not match partial names or mid-sentence locations. Improve the single extra gsub.')
 report={'model':lab.MODEL,'baseline':'74/76 after first candidate','attempts':[],
         'model_authored_verified_76':False}
 try:
  for i in range(2):
   attempt={'attempt':i+1}
   try:
    proposed=lab.ask_model(fn,feedback)
    line=lab.canonicalize(proposed)
    attempt['raw_proposal']=proposed;attempt['canonical_proposal']=line
    if not lab.allowed(line):
     attempt['status']='REJECTED_GUARD'
     feedback='Rejected: malformed one-line Lua gsub. Return strict JSON replacement_line.'
    else:
     result=eval_patch(line)
     attempt['hidden_tests']=result
     attempt['status']='VERIFIED' if result['passed'] else 'FAILED'
     if result['passed']:report['model_authored_verified_76']=True
     feedback='The Lua 5.1 suite still fails. Try a broader safe end-of-string punctuation pattern.'
   except Exception as exc:
    attempt['status']='ERROR';attempt['error']=type(exc).__name__
   report['attempts'].append(attempt)
   if report['model_authored_verified_76']:break
 finally:
  report['original_unchanged']=before==[lab.digest(src),lab.digest(tst)]
  REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 return report
if __name__=='__main__':
 print(json.dumps(run(),ensure_ascii=True)[:3000],flush=True)
