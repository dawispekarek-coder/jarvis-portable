"""Deterministic Lua 5.1 repair-skill demonstration, NOT model-authored code.
Enumerate tightly constrained patterns; validate only in disposable fixture.
"""
import json,hashlib,shutil,subprocess,tempfile,difflib
from pathlib import Path
import lua_coding_lab as lab
import knowledge_coding_gate as gate
from lua_holdout_eval import INS
from pattern_feedback_pilot import HIDDEN,assemble

ROOT=lab.ROOT
REPORT=ROOT/'reports'/'guarded_synthesis.json'

# Limited documented Lua string-pattern grammar; never arbitrary model code.
PATTERNS=('%p+$','[%.!?:]+$','[%.!?]+$')

PROPERTIES='''-- Property checks introduced AFTER the selected candidate passes 76
local propNames={"Thork","Bloodhoof Village","Mulgore","Sharing the Land"}
local propPunctuation={".","!","?",":",";","...",",",")","?!","!!!"}
for _,name in ipairs(propNames) do
 for _,punct in ipairs(propPunctuation) do
  check(UIV2.NavRepeatsTitle(name,"Talk to "..name..punct),"property: trailing punctuation")
  check(not UIV2.NavRepeatsTitle(name,"Talk to "..name.."town"..punct),"property: distinct suffix")
  check(not UIV2.NavRepeatsTitle(name,"Talk to "..name.." then continue"..punct),"property: intermediate destination")
 end
end
'''

def hashes():
    return {n:lab.digest(lab.F/n) for n in ('ForeverRoute_UIv2.lua','tests/now_card_objectives.lua')}
def property_gate(candidate):
    raw,start,end,fragment=gate.source_section()
    if not lab.allowed(candidate):return {'passed':False,'reason':'guard'}
    baseline=hashes()
    target=ROOT/'coding_runs';target.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='property_gate_',dir=target) as name:
        d=Path(name);(d/'tests').mkdir()
        for dep in ('ForeverRoute.lua','ForeverRoute_UIAdapter.lua'):
            shutil.copy2(lab.F/dep,d/dep)
        source=d/'ForeverRoute_UIv2.lua'
        source.write_text(raw[:start]+fragment.replace(lab.OLD,candidate,1)+raw[end:],encoding='utf-8')
        test=(lab.F/'tests'/'now_card_objectives.lua').read_text(encoding='utf-8')
        marker='-- --------------------------------------------------------------- report'
        if test.count(marker)!=1:raise ValueError('Test marker ambiguous')
        test=test.replace(marker,INS+HIDDEN+PROPERTIES+marker)
        suite=d/'tests'/'now_card_objectives.lua'
        suite.write_text(test,encoding='utf-8')
        sha=lab.digest(suite)
        proc=subprocess.run([str(lab.LUA),str(suite),str(d)],cwd=d,
           capture_output=True,text=True,errors='replace',timeout=20)
        tail=proc.stdout[-900:]
        safe=(baseline==hashes() and sha==lab.digest(suite))
        return {'passed':proc.returncode==0 and '204 checks, 0 failures' in tail and safe,
                'returncode':proc.returncode,'test_summary':tail,'sources_unchanged':safe}
def export_review_patch(candidate):
    """Preview-only unified diff, not applied anywhere."""
    raw,start,end,fragment=gate.source_section()
    if not lab.allowed(candidate):raise ValueError('not allowlisted')
    updated=raw[:start]+fragment.replace(lab.OLD,candidate,1)+raw[end:]
    if raw==updated or fragment.count(lab.OLD)!=1:raise ValueError('not a single change')
    before=raw.splitlines(keepends=True)
    after=updated.splitlines(keepends=True)
    delta=''.join(difflib.unified_diff(before,after,
        fromfile='a/ForeverRoute_UIv2.lua',tofile='b/ForeverRoute_UIv2.lua',n=3))
    if delta.count('@@ ' )!=1:raise ValueError('unexpected number of hunks')
    result=ROOT/'reports'/'foreverroute_nav_review_only.patch'
    result.parent.mkdir(exist_ok=True)
    result.write_text(delta,encoding='utf-8')
    return str(result)
def synthesize():
    before=hashes()
    result={'method':'deterministic limited Lua pattern enumeration',
            'model_authored':False,'current_run_used_model':False,
            'human_defined_pattern_grammar':True,
            'selected_pattern':None,'verified_204':False,'candidates':[]}
    for pattern in PATTERNS[:6]:
        entry={'pattern':pattern,'public_status':'NOT_TESTED'}
        try:
            line=assemble(pattern)
            check=gate.evaluate_candidate(line)
            entry['public_status']=check['status']
            if check['status']=='VERIFIED_76':
                result['selected_pattern']=pattern
                result['candidate']=line
                result['property_gate']=property_gate(line)
                result['verified_204']=result['property_gate']['passed']
                entry['status']='SELECTED'
                result['candidates'].append(entry)
                break
            entry['status']='NOT_VERIFIED'
        except Exception as exc:
            entry['status']='REJECTED'
            entry['error']=type(exc).__name__
        result['candidates'].append(entry)
    result['original_unchanged']=before==hashes()
    result['verified_204']=bool(result['verified_204'] and result['original_unchanged'])
    if result['verified_204'] and result['selected_pattern'] is not None:
        result['review_patch']=export_review_patch(result['candidate'])
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':print(json.dumps(synthesize(),ensure_ascii=True)[:1600],flush=True)