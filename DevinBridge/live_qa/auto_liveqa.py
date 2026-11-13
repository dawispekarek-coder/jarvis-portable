"""Persistent, scoped automatic ForeverRoute smoke QA. No gameplay bot.

When the desktop is unlocked and idle, no WoW/game or Devin worker is
running, this verifies one stable addon build, deploys it with a byte-preserving
backup, opens Battle.net UI, tests a saved character, then either KEEPS on
clean PASS or ROLLS BACK on warning/failure. Never publishes/reaches accounts.
"""
from __future__ import annotations
import hashlib,json,msvcrt,os,subprocess,sys,time,traceback
from pathlib import Path
from datetime import datetime,timezone
from contextlib import contextmanager
from lupa import LuaRuntime
import qa_manager as qa
import ui_agent as ui
import qa_observer

ROOT=Path(__file__).resolve().parent
STATE=ROOT/'auto_state.json'
LOCK=ROOT/'auto_liveqa.lock'
STOP=ROOT/'LIVEQA_STOP.flag'
HEALTH=ROOT/'auto_health.json'
AGENT_ROOT=ROOT.parent

def now():return datetime.now(timezone.utc).isoformat()
def write_json(path,value):
    t=path.with_suffix(path.suffix+'.tmp')
    t.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    os.replace(t,path)
def read_json(path):
    if not path.exists():return {}
    return json.loads(path.read_text(encoding='utf-8'))
@contextmanager
def one_instance():
    with LOCK.open('a+b') as f:
        f.seek(0);f.write(b'0');f.flush();f.seek(0)
        try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise RuntimeError('LiveQA already active')
        try:yield
        finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
def workers_busy():
    ps=subprocess.run(['powershell','-NoProfile','-Command',
      'Get-CimInstance Win32_Process|Where-Object {$_.Name -eq "python.exe" -and $_.CommandLine -match "DevinBridge.prompt_worker"}|Select-Object -ExpandProperty ProcessId'],
      capture_output=True,text=True,timeout=15)
    if ps.returncode != 0:
        return True  # Cannot verify workers, do not deploy.
    if ps.stdout.strip():
        return True
    # A coordinator task may be actively owned by a GUI Devin session,
    # even if no Python prompt_worker is visible.
    try:
        tasks=read_json(AGENT_ROOT/'coordinator_state.json').get('tasks') or {}
        return any(t.get('status') in ('RUNNING','DISPATCHED','VERIFYING','NEEDS_APPROVAL')
                   for t in tasks.values())
    except (OSError,ValueError,TypeError,AttributeError):
        return True  # Fail closed on unreadable task state.
def addon_files(folder):
    found=[]
    for p in folder.rglob('*'):
        if not p.is_file() or p.is_symlink():continue
        rel=p.relative_to(folder)
        if len(rel.parts)==1:
            if p.suffix.lower() not in qa.ALLOWED_EXT:continue
        elif rel.parts[0] not in qa.ALLOWED_DIRS:
            continue
        if p.suffix.lower() not in qa.ALLOWED_EXT:continue
        found.append((rel.as_posix(),p))
    return sorted(found)
def fingerprint(folder):
    h=hashlib.sha256()
    files=addon_files(folder)
    if len(files)<30:raise RuntimeError('Too few addon assets for safe deploy')
    for name,p in files:
        h.update(name.encode('utf-8'));h.update(b'\0')
        h.update(qa.sha(p).encode('ascii'));h.update(b'\0')
    return h.hexdigest(),len(files)
def source_stable():
    files=addon_files(qa.SOURCE)
    if len(files)<30:raise RuntimeError('No complete source addon')
    newest=max(p.stat().st_mtime for _,p in files)
    return time.time()-newest>=180

def safety_preflight():
    if STOP.exists() or ui.stop():return 'OWNER_STOP'
    if qa.wow_running():return 'WOW_ALREADY_RUNNING'
    if workers_busy():return 'DEVIN_BUSY'
    if (AGENT_ROOT/'PAUSED.flag').exists():return 'JARVIS_PAUSED'
    if ui.locked():return 'DESKTOP_LOCKED'
    if tuple(ui.pg.size())!=(1920,1080):
        return 'SCREEN_RESOLUTION_NOT_SUPPORTED'
    if ui.idle()<600:return 'OWNER_NOT_IDLE'
    return None

def offline_tests():
    v=qa.verify_toc(qa.STAGE)
    lua=LuaRuntime(unpack_returned_tuples=True)
    compiler=lua.eval('load')
    files=list(qa.STAGE.rglob('*.lua'))
    if len(files)<30:raise RuntimeError('Offline QA found insufficient Lua files')
    for f in files:
        code=compiler(f.read_text(encoding='utf-8-sig',errors='replace'),'@'+str(f))
        if isinstance(code,tuple) or not callable(code):
            raise RuntimeError('Lua compile failure: '+str(f.relative_to(qa.STAGE)))
    test=qa.SOURCE/'tests'/'test_route_nav_evidence_audit.py'
    if test.exists():
        p=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests',
                        '-p','test_route_nav_evidence_audit.py'],cwd=qa.SOURCE,
                        capture_output=True,text=True,timeout=150)
        if p.returncode:raise RuntimeError('Regression tests failed: '+p.stderr[-750:])
    return {'lua_files':len(files),'toc_files':v['files_in_toc']}
def refresh_stage(expected_signature):
    # Preserve prior staging; never delete files automatically.
    if qa.STAGE.exists():
        hist=ROOT/'staged_history'
        hist.mkdir(exist_ok=True)
        dest=hist/('prior_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
        if dest.exists():raise RuntimeError('Staging archive collision')
        qa.STAGE.rename(dest)
    qa.stage_candidate()
    actual,_=fingerprint(qa.STAGE)
    if actual!=expected_signature:
        raise RuntimeError('Source changed while staging candidate')

def recover_orphan():
    if not qa.MANIFEST.exists():return False
    m=read_json(qa.MANIFEST)
    if not m.get('active'):return False
    if qa.wow_running():raise RuntimeError('Active candidate with WoW running: manual safety stop')
    qa.rollback()
    return True

def watch_once():
    with one_instance():
        before=read_json(STATE)
        if recover_orphan():
            write_json(STATE,{**before,'at':now(),'status':'INTERRUPTED_CANDIDATE_RESTORED'})
            return 'INTERRUPTED_CANDIDATE_RESTORED'
        reason=safety_preflight()
        if reason:return reason
        if not source_stable():return 'SOURCE_NOT_STABLE_FOR_3_MIN'
        src_sig,src_files=fingerprint(qa.SOURCE)
        if before.get('last_signature')==src_sig:
            return 'ALREADY_TESTED_'+str(before.get('last_result','UNKNOWN'))
        if before.get('last_result')=='KEPT_VERIFIED':
            installed_sig,_=fingerprint(qa.LIVE)
            if installed_sig==src_sig:
                return 'VERIFIED_INSTALL_ALREADY_CURRENT'
        try:
            refresh_stage(src_sig)
            offline=offline_tests()
        except Exception as e:
            write_json(STATE,{'last_signature':src_sig,'last_result':'OFFLINE_FAILED',
                 'last_at':now(),'last_record':{'reason':str(e)}})
            return 'OFFLINE_FAILED'
        if fingerprint(qa.SOURCE)[0]!=src_sig or workers_busy():
            raise RuntimeError('Source/worker changed during offline QA')
        reason=safety_preflight()
        if reason:return 'PRE_DEPLOY_'+reason
        write_json(STATE,{'last_signature':src_sig,'last_result':'DEPLOY_IN_PROGRESS',
                          'last_at':now()})
        deployed=qa.deploy_candidate(allow_live=True)
        record={'at':now(),'signature':src_sig,'files':src_files,
                'offline':offline,'deployed_backup':deployed['backup']}
        try:
            run=ui.run()
            record['in_game']=run
            if (run.get('state')=='COMPLETE' and
                run.get('qa',{}).get('result')=='PASS' and
                not run.get('protected_popup_seen')):
                kept=qa.keep_verified(run)
                record['result']='KEPT_VERIFIED'
                record['backup']=kept['backup']
            else:
                qa.rollback()
                record['result']='ROLLBACK_NOT_CLEAN_PASS'
        except Exception as exc:
            record['error']=str(exc)
            if qa.wow_running():
                record['result']='ATTENTION_WOW_ACTIVE_BACKUP_NOT_RESTORED'
            else:
                try:
                    qa.rollback()
                    record['result']='ROLLED_BACK_AFTER_ERROR'
                except Exception as restore_error:
                    record['result']='ROLLBACK_REQUIRES_HUMAN'
                    record['rollback_error']=str(restore_error)
        finally:
            write_json(STATE,{'last_signature':src_sig,
                'last_result':record.get('result','UNRESOLVED'),
                'last_at':now(),'last_record':record})
            try:qa_observer.collect()
            except Exception:pass
        return record['result']
def notify_result(outcome):
    important=('KEPT_VERIFIED','ROLLBACK_NOT_CLEAN_PASS',
      'ROLLED_BACK_AFTER_ERROR','ROLLBACK_REQUIRES_HUMAN',
      'ATTENTION_WOW_ACTIVE_BACKUP_NOT_RESTORED','OFFLINE_FAILED')
    if outcome not in important:return
    try:
        from DevinBridge.notify import Notifier
        msg=('New ForeverRoute kept after real WoW smoke PASS. Backup retained.'
             if outcome=='KEPT_VERIFIED' else
             'Live QA did not pass: '+outcome+'. Previous addon restored if WoW was closed; check Jarvis Live.')
        Notifier(AGENT_ROOT)._send_raw('ForeverRoute Live QA',msg,'3' if outcome=='KEPT_VERIFIED' else '4',
                                      'robot,white_check_mark' if outcome=='KEPT_VERIFIED' else 'robot,warning')
    except Exception:
        pass  # Notification transport may be down; results remain on disk.

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--check',action='store_true',help='read-only preflight')
    a=ap.parse_args()
    if a.check:
        result={'mode':'READ_ONLY','at':now(),'preflight':safety_preflight(),
            'source_stable':source_stable(),
            'source_fingerprint':fingerprint(qa.SOURCE)[0],
            'installed_fingerprint':fingerprint(qa.LIVE)[0],
            'last_automation':read_json(STATE)}
        print(json.dumps(result,ensure_ascii=False,indent=2));return
    try:
        outcome=watch_once()
        health={'at':now(),'outcome':outcome,'automatic':True}
        write_json(HEALTH,health)
        notify_result(outcome)
        print(json.dumps(health,ensure_ascii=False))
    except Exception as exc:
        health={'at':now(),'outcome':'ERROR','reason':str(exc),
                'automatic':True}
        write_json(HEALTH,health)
        print(json.dumps(health,ensure_ascii=False),file=sys.stderr)
        raise SystemExit(2)

if __name__=='__main__':main()
