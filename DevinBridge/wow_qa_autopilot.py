"""Jarvis-owned bounded 24h WoW QA. No unattended gameplay bot."""
from __future__ import annotations
import json, os, subprocess, sys, time
from pathlib import Path
from .bridge_store import atomic_write_json, read_json, SUBPROCESS_NO_WINDOW
from . import trial_scope
BRIDGE=Path(__file__).resolve().parent
TRIAL=BRIDGE/trial_scope.TRIAL
STATE_FILE=BRIDGE/'wow_qa_autopilot_state.json'
WORK=BRIDGE/'autonomy_scope'/'workspaces'/'foreverroute-route-audit'
OUT=WORK/'tools'/'wow_qa_autopilot_latest.json'
LOG=BRIDGE/'wow_qa_autopilot.log'

def valid_trial(now=None):
    now=time.time() if now is None else now
    grant=read_json(BRIDGE/'autonomy_scope'/'CDP_PROGRAM.json',{})
    d=read_json(TRIAL,{})
    prog=trial_scope.extend_program(BRIDGE,grant,now=now)
    return bool(prog.get('trial_active') and d.get('allow_wow_client_qa') is True and d.get('wow_qa_no_client_file_changes') is True and d.get('wow_qa_no_gameplay_bot') is True),d

def pid_running(pid):
    """Windows process-handle check; no optional psutil dependency."""
    try:
        import ctypes
        kernel=ctypes.windll.kernel32
        handle=kernel.OpenProcess(0x00100000,False,int(pid))
        if not handle: return False
        try: return kernel.WaitForSingleObject(handle,0)==0x00000102
        finally: kernel.CloseHandle(handle)
    except (ValueError,TypeError,OSError,AttributeError): return False
def run_once():
    okay,grant=valid_trial()
    if not okay:
        print('TRIAL_EXPIRED_OR_NOT_ALLOWED',flush=True)
        return 3
    from . import wow_qa
    report={'ts':time.time(),'scope':'24h-owner-trial',
      'valid_until':grant.get('expires_utc'),
      'qa_level':'client_launch_and_observation_only','gameplay_bot':False}
    try:
        report['observation']=wow_qa.run(wait_seconds=120)
        result=report['observation']
        report['result']=result.get('result','UNKNOWN')
        report['interactive_qa']='AUTOMATION_GAP' if result.get('interactive_qa') else 'UNKNOWN'
        report['next_action']='Jarvis must develop verifiable automated in-game QA from collected evidence, not treat launch as route PASS.'
    except Exception as e:
        report['result']='ERROR'
        report['error']=f'{type(e).__name__}: {str(e)[:400]}'
    report['finished']=time.time()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    atomic_write_json(OUT,report)
    print(json.dumps({'result':report['result'],'path':str(OUT),
      'error':report.get('error','')},ensure_ascii=False),flush=True)
    return 0 if report['result']=='VERIFIED_LAUNCH' else 1
def _propose_followup(coord, state, report):
    if state.get('followup_created') or not report:
        return state
    from . import cdp
    prompt=(
      'Jarvis 24h WoW QA has collected real client evidence in '
      'tools/wow_qa_autopilot_latest.json and tools/wow_qa_latest.json. '
      'Read those artifacts and available screenshots. Automate reliable '
      'non-bot in-game addon checks: visible NOW target, eligibility, zone '
      'bounce, and UI taint after addon load. Use real SavedVariables and '
      'observable screenshots where possible. If login/interaction prevents '
      'an assertion mark UNKNOWN; never fake PASS or claim launch means route QA. '
      'Create tools/wow_auto_qa_feedback.json plus runnable '
      'tests/test_wow_auto_qa_feedback.py, document actionable defects. '
      'All edits in authorized worktree; no SavedVariables modifications, '
      'questing bot, publishing, client addon deploy, or credentials.')
    res=cdp.new_issue_proposal(coord,kind='test-add',
      title='Build unattended ForeverRoute in-game QA from real client evidence',
      prompt=prompt,worktree=str(WORK),
      signature='24h-wowqa-evidence-to-in-game-checks-v1',
      evidence_refs=['tools/wow_qa_autopilot_latest.json'],
      acceptance=[{'type':'file_exists','path':'tools/wow_auto_qa_feedback.json'},
        {'type':'test','runner':'unittest','args':['tests.test_wow_auto_qa_feedback'],'timeout':180}],priority=15)
    if res.get('ok'):
        state['followup_created']=res.get('proposal_id')
    return state
def tick(coord):
    now=time.time()
    okay,trial=valid_trial(now)
    state=read_json(STATE_FILE,{})
    if not okay:
        if state.get('status')!='EXPIRED':
            state.update(status='EXPIRED',updated=now)
            atomic_write_json(STATE_FILE,state)
        return {'state':'EXPIRED'}
    report=read_json(OUT,{})
    if report.get('finished') and report.get('finished')!=state.get('last_report_ts'):
        state['last_report_ts']=report['finished']
        state['last_result']=report.get('result')
        state['last_interactive_qa']=report.get('interactive_qa')
        state=_propose_followup(coord,state,report)
    pid=state.get('worker_pid')
    if pid and pid_running(pid):
        state.update(status='RUNNING',updated=now)
        atomic_write_json(STATE_FILE,state)
        return {'state':'RUNNING','pid':pid}
    if pid: state['worker_pid']=None
    interval=max(900,min(int(trial.get('wow_qa_interval_minutes',30))*60,3600))
    if now-float(state.get('last_started',0))<interval:
        state.update(status='COOLDOWN',updated=now)
        atomic_write_json(STATE_FILE,state)
        return {'state':'COOLDOWN','last_result':state.get('last_result')}
    if now+240>=float(trial.get('expires_epoch',0)):
        state.update(status='EXPIRING',updated=now)
        atomic_write_json(STATE_FILE,state)
        return {'state':'EXPIRING'}
    LOG.parent.mkdir(parents=True,exist_ok=True)
    with LOG.open('ab') as f:
        p=subprocess.Popen([sys.executable,'-m','DevinBridge.wow_qa_autopilot','--run'],
          cwd=str(BRIDGE.parent),stdin=subprocess.DEVNULL,stdout=f,stderr=f,
          creationflags=SUBPROCESS_NO_WINDOW)
    state.update(worker_pid=p.pid,last_started=now,status='RUNNING',updated=now)
    atomic_write_json(STATE_FILE,state)
    return {'state':'STARTED','pid':p.pid}

if __name__=='__main__':
    if '--run' in sys.argv:
        raise SystemExit(run_once())
    from .daemon import make_coordinator,load_config
    print(tick(make_coordinator(load_config())))