"""Passive WoW Forever QA observer. No UI clicks, no credentials, no game mutations."""
from __future__ import annotations
import json, time
from datetime import datetime, timezone
from pathlib import Path
from qa_manager import status

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'status.json'


def emit_cdpevidence(diag):
    """Only real recent SaveVariables results; no writes to live WoW files."""
    from qa_manager import SOURCE
    parent=ROOT.parent
    queue=parent/'coordinator_state.json'
    try:
        tasks=json.loads(queue.read_text(encoding='utf-8'))['tasks']
        if any(t.get('status') in ('RUNNING','DISPATCHED','VERIFYING','NEEDS_APPROVAL')
               for t in tasks.values()):
            return
    except (OSError,ValueError,KeyError):
        return
    target=SOURCE/'tools'/'liveqa_results.json'
    if not target.parent.is_dir():return
    result=diag['result']
    proof=(f'Observed from real WoW Forever SavedVariables after client login/reload. '
           f'Probe result={result}, health={diag.get("health")}, phase={diag.get("phase")}, degraded_modules={diag.get("degraded_modules", [])}. '
           'This does NOT prove all route levels 1-60. '
           'Lua global error capturing is not instrumented.')
    entry={'name':'ForeverRoute_live_load_smoke', 'ok':result=='PASS',
           'error':proof, 'path':'docs/autonomy',
           'fix_file':'docs/autonomy/live_qa_load_triage.md',
           'rerun':'Open via Battle.net, enter a test character, /reload, logout, inspect QA probe'}
    payload={'source':'real_wow_forever_live_qa', 'tests':[entry]}
    text=json.dumps(payload,ensure_ascii=False,indent=2)
    if target.exists() and target.read_text(encoding='utf-8')==text:
        return
    target.write_text(text,encoding='utf-8')


def collect():
    s=status()
    diag=s['diagnostic']
    if not s['probe_installed']:
        phase='PROBE_NOT_INSTALLED'
    elif (diag.get('state')=='LIVE_RESULT_RECORDED' and
          diag.get('age_seconds',999999) <= 3600):
        phase='RESULT_'+diag.get('result','UNKNOWN')
    elif s['wow_running']:
        phase='GAME_RUNNING_AWAIT_SAVED_VARIABLES'
    elif diag.get('state')!='LIVE_RESULT_RECORDED':
        phase='WAITING_FOR_BATTLENET_PLAY_AND_CHARACTER_LOGIN'
    else:
        phase='STALE_GAME_RESULT'
    payload={'checked_at':datetime.now(timezone.utc).isoformat(),
             'phase':phase,'wow_running':s['wow_running'],
             'probe_installed':s['probe_installed'],
             'candidate_active':s['candidate_active'],
             'result':diag,'launch_method':'Battle.net GUI, existing login only',
             'script_errors':'NOT_INSTRUMENTED',
             'confirmed_by_actual_game':diag.get('state')=='LIVE_RESULT_RECORDED'}
    OUT.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    # Feed independently observed game failures to the isolated CDP queue.
    # Never claim a result from mere process existence or a simulated test.
    if (diag.get('state')=='LIVE_RESULT_RECORDED' and
            diag.get('result') in ('FAIL','WARN','PASS') and
            diag.get('age_seconds',999999) <= 86400):
        emit_cdpevidence(diag)
    return payload

if __name__=='__main__':
    result=collect()
    print(result['phase'])
