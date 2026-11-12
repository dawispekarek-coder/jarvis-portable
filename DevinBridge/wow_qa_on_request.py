"""Start WoW QA ONLY after a specific Devin report requests in-game verification.
No interval, no unattended game-playing, and no invented gameplay PASS.
"""
from __future__ import annotations
import hashlib, json, re, subprocess, sys, time
from pathlib import Path
from .bridge_store import atomic_write_json, read_json, SUBPROCESS_NO_WINDOW
from . import trial_scope
ROOT=Path(__file__).resolve().parent
WORK=ROOT/'autonomy_scope'/'workspaces'/'foreverroute-route-audit'
STATE=ROOT/'wow_qa_on_request_state.json'
RESULT=WORK/'tools'/'wow_qa_on_request_latest.json'
LOG=ROOT/'wow_qa_on_request.log'
REQUEST=re.compile(r'(?i)(?:INGAME_QA_REQUIRED|in[-_ ]?game\s+(?:QA|test|verification|validation)|(?:test|verify|check)\s+(?:it\s+)?in[-_ ]?game|(?:herni|herní)\s+(?:test|overeni|ověření)|requires_human.{0,90}(?:game|wow))')
NEED=re.compile(r'(?i)(?:outstanding|remain|pending|need|require|manual|human|block|unverif|unprov|chyb|nutn|vyzadu|vyžadu|must|not tested|not verified)')

def authorization(now=None):
    now=time.time() if now is None else float(now)
    program=read_json(ROOT/'autonomy_scope'/'CDP_PROGRAM.json',{})
    trial=read_json(ROOT/trial_scope.TRIAL,{})
    valid=trial_scope.extend_program(ROOT,program,now=now)
    okay=(valid.get('trial_active') and trial.get('allow_wow_client_qa') is True
       and trial.get('qa_trigger')=='only_after_explicit_Devin_ingame_verification_request'
       and trial.get('wow_qa_no_gameplay_bot') is True
       and trial.get('wow_qa_no_client_file_changes') is True)
    return bool(okay),trial

HUMAN_WOW=re.compile(r'(?i)HUMAN[-_ ]ONLY.{0,160}(?:in[- ]game|wow|client|ve\s+hre|ve\s+hře)')

def explicit_qa_request(text, delegated=False):
    if not isinstance(text,str): return ''
    for match in REQUEST.finditer(text[-6000:]):
        chunk=text[max(0,match.start()-140):min(len(text),match.end()+150)]
        if NEED.search(chunk) and not re.search(r'(?i)(?:not\s+(?:necessary|required)|no\s+(?:need|requirement))',chunk):
            return chunk.strip()[:300]
    # delegated WoW-client human gates act as an implicit QA request
    # (owner grant 2026-11-12, trial window only)
    if delegated:
        m = HUMAN_WOW.search(text[-6000:])
        if m:
            return ('delegated-wow-gate: ' +
                    m.group(0)[:260]).strip()
    return ''
def alive(pid):
    try:
        import ctypes
        k=ctypes.windll.kernel32
        h=k.OpenProcess(0x00100000,False,int(pid))
        if not h:return False
        try:return k.WaitForSingleObject(h,0)==0x00000102
        finally:k.CloseHandle(h)
    except (ValueError,TypeError,OSError,AttributeError):return False

def _epoch(ts):
    from datetime import datetime
    try:return datetime.fromisoformat(str(ts).replace('Z','+00:00')).timestamp()
    except (ValueError,TypeError):return 0

def _candidate(coord, state, trial):
    chosen=[]
    for t in coord.list_tasks():
        if t.get('status') not in ('COMPLETE','NEEDS_REVIEW','FAILED'):continue
        if str(t.get('worktree','')).casefold()!=str(WORK).casefold():continue
        # Existing P0 game-QA request was made just before the trial started.
        if t.get('id')!='GEN-81475D6D5C' and _epoch(t.get('updated_at'))<float(trial['starts_epoch']):continue
        evidence=explicit_qa_request(
            t.get('agent_text_tail',''),
            delegated=bool(trial.get('delegate_wow_client_actions')))
        if not evidence:continue
        key=hashlib.sha256((str(t['id'])+'|'+str(t.get('updated_at'))+'|'+evidence).encode()).hexdigest()[:20]
        if key in state.get('handled',[]):continue
        chosen.append((t,evidence,key))
    chosen.sort(key=lambda x:x[0].get('updated_at',''),reverse=True)
    return chosen[0] if chosen else None

def run_requested(request):
    ok,trial=authorization()
    if not ok or time.time()+240>=float(trial.get('expires_epoch',0)):
        return 3
    from . import wow_qa
    report={'task_id':request['task_id'],'request_key':request['request_key'],
      'requested_by':'Devin agent report','request_excerpt':request['evidence'],
      'started':time.time(),'qa_mode':'client and UI observation, no gameplay bot'}
    try:
        report['observation']=wow_qa.run(wait_seconds=120)
        report['result']=report['observation'].get('result','UNKNOWN')
        report['actual_route_qa']='UNKNOWN'
    except Exception as e:
        report['result']='ERROR'
        report['error']=type(e).__name__+': '+str(e)[:250]
    report['finished']=time.time()
    atomic_write_json(RESULT,report)
    print(json.dumps({'task':request['task_id'],'result':report['result'],
      'route_qa':report['actual_route_qa']},ensure_ascii=False),flush=True)
    return 0 if report['result']=='VERIFIED_LAUNCH' else 1
def _followup(coord, state, report):
    if state.get('followup_key')==report.get('request_key'):return
    if report.get('actual_route_qa')!='UNKNOWN':return
    from . import cdp
    prompt=(
      'Devin explicitly requested WoW in-game QA. Jarvis already attempted '
      'the real client. Inspect tools/wow_qa_on_request_latest.json and '
      'tools/wow_qa_latest.json; actual quest routing remains UNKNOWN. '
      'Implement bounded automated addon UI QA via real screenshots and '
      'read-only game-state evidence for quest eligibility and zone bouncing. '
      'Never treat client launch as gameplay PASS or invent route results. '
      'Do not bot questing, write WoW files, access credentials or publish. '
      'Write tools/wow_qa_route_followup.json and executable tests.')
    res=cdp.new_issue_proposal(coord,kind='test-add',
      title='Automate in-game route QA requested by Devin',
      prompt=prompt,worktree=str(WORK),
      signature='in-game-qa-request-'+str(report.get('task_id','')),
      evidence_refs=['tools/wow_qa_on_request_latest.json'],
      acceptance=[{'type':'file_exists','path':'tools/wow_qa_route_followup.json'},
       {'type':'test','runner':'unittest','args':['tests.test_route_quality_validator'],'timeout':180}],
      priority=10)
    state['followup_key']=report.get('request_key')
    state['followup']=res

def tick(coord) -> dict:
    """Daemon entry: run WoW QA ONLY when a Devin report explicitly
    asks for in-game verification. No schedule, no idle launches."""
    ok, trial = authorization()
    state = read_json(STATE, {})
    if not ok:
        state['last'] = {'ts': time.time(), 'result': 'UNAUTHORIZED'}
        atomic_write_json(STATE, state)
        return {'qa': 'unauthorized'}
    if state.get('running_pid') and alive(state['running_pid']):
        return {'qa': 'busy'}
    cand = _candidate(coord, state, trial)
    if not cand:
        return {'qa': 'idle'}
    t, evidence, key = cand
    req = {'task_id': t['id'], 'request_key': key, 'evidence': evidence}
    try:
        code = run_requested(req)
        err = ''
    except Exception as e:  # noqa: BLE001 — record ERROR, never fake PASS
        code, err = 1, str(e)[:160]
    handled = list(state.get('handled') or [])
    handled.append(key)
    state.update({'handled': handled[-50:],
                  'last': {'ts': time.time(), 'task_id': t['id'],
                           'exit': code, 'error': err}})
    rep = read_json(RESULT, {})
    if rep.get('actual_route_qa') != 'VERIFIED':
        _followup(coord, state, {'request_key': key,
                                 'task_id': t['id'],
                                 'actual_route_qa': 'UNKNOWN'})
    atomic_write_json(STATE, state)
    return {'qa': 'ran', 'task_id': t['id'], 'exit': code}
