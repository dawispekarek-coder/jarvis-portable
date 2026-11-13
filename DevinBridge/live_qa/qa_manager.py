"""Safe WoW Forever Live QA deploy/rollback. No account or gameplay automation."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WOW = Path(r'H:\World of Warcraft\_forever_')
ADDONS = WOW / 'Interface' / 'AddOns'
LIVE = ADDONS / 'ForeverRoute'
PROBE = ADDONS / 'ForeverRouteLiveQA'
SOURCE = Path(r'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\autonomy_scope\workspaces\foreverroute-route-audit')
STAGE = HERE / 'staged' / 'ForeverRoute'
BACKUPS = HERE / 'backups'
MANIFEST = HERE / 'deployment.json'
EXCLUDE = {'.git', '.github', 'tests', 'tools', 'docs', '__pycache__', '.venv', '.idea', '.vscode'}
ALLOWED_DIRS = {'DB', 'Generated', 'libs', 'Media'}
ALLOWED_EXT = {'.lua', '.xml', '.toc', '.tga', '.blp', '.png', '.jpg', '.jpeg', '.ttf', '.otf'}


def wow_running() -> bool:
    p = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Wow.exe'], capture_output=True, text=True, errors='replace', timeout=12)
    return 'Wow.exe' in p.stdout


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def verify_toc(folder: Path) -> dict:
    toc = folder / 'ForeverRoute.toc'
    if not toc.is_file():
        raise RuntimeError('ForeverRoute.toc is missing')
    files = []
    for line in toc.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        rel = Path(line.replace('\\', '/'))
        if rel.is_absolute() or '..' in rel.parts:
            raise RuntimeError('Forbidden TOC path: ' + line)
        if not (folder/rel).is_file():
            raise RuntimeError('TOC file missing: '+line)
        files.append(rel.as_posix())
    return {'files_in_toc':len(files), 'toc_sha256':sha(toc)}


def save(payload: dict) -> None:
    HERE.mkdir(parents=True,exist_ok=True)
    MANIFEST.write_text(json.dumps(payload, indent=2),encoding='utf-8')

def install_probe() -> dict:
    if wow_running():
        raise RuntimeError('WoW active: cannot change AddOns while in game')
    src=HERE/'ForeverRouteLiveQA'
    if not (src/'ForeverRouteLiveQA.toc').is_file():
        raise RuntimeError('Probe source missing')
    if PROBE.exists():
        for name in ('ForeverRouteLiveQA.lua','ForeverRouteLiveQA.toc'):
            if sha(PROBE/name)!=sha(src/name):
                raise RuntimeError('Different probe installed, refuse overwrite')
        return {'state':'ALREADY_INSTALLED','path':str(PROBE)}
    shutil.copytree(src,PROBE)
    return {'state':'PROBE_INSTALLED','path':str(PROBE),
            'toc_sha256':sha(PROBE/'ForeverRouteLiveQA.toc')}


def stage_candidate() -> dict:
    if wow_running():
        raise RuntimeError('Cannot stage while WoW running')
    if STAGE.exists():
        raise RuntimeError('Existing staged candidate: inspect or clear manually')
    if not (SOURCE/'.git').exists():
        raise RuntimeError('Approved isolated worktree missing .git')
    # Never follow a nested symlink out of the designated isolated worktree.
    if any(p.is_symlink() for p in SOURCE.rglob('*')):
        raise RuntimeError('Symlink in addon worktree; stage refused')
    STAGE.parent.mkdir(parents=True,exist_ok=True)
    STAGE.mkdir()
    for item in SOURCE.iterdir():
        if item.is_symlink() or item.name in EXCLUDE:
            continue
        if item.is_file() and item.suffix.lower() in ALLOWED_EXT:
            shutil.copy2(item,STAGE/item.name)
        elif item.is_dir() and item.name in ALLOWED_DIRS:
            shutil.copytree(item,STAGE/item.name,
                ignore=shutil.ignore_patterns('.git','__pycache__','*.bak','*.tmp','*.pyc'))
    v=verify_toc(STAGE)
    result={'state':'CANDIDATE_STAGED','staged_at':datetime.now(timezone.utc).isoformat(),
        'source':str(SOURCE),'staged_toc_sha256':v['toc_sha256'],
        'files_in_toc':v['files_in_toc']}
    (HERE/'stage.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

def deploy_candidate(allow_live=False) -> dict:
    if not allow_live:
        raise RuntimeError('Explicit --allow-live required for client installation')
    if wow_running():
        raise RuntimeError('WoW running: never swap installed files')
    verify_toc(STAGE)
    if MANIFEST.exists():
        old=json.loads(MANIFEST.read_text(encoding='utf-8'))
        if old.get('active'):
            raise RuntimeError('QA candidate already active; restore first')
    backup_dir=WOW/'ForeverRoute_Backups'
    backup_dir.mkdir(exist_ok=True)
    backup=backup_dir/('ForeverRoute_LiveQA_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
    tmp=ADDONS/'.ForeverRouteLiveQA_staging'
    if backup.exists() or tmp.exists() or not LIVE.is_dir():
        raise RuntimeError('Deployment collision or live ForeverRoute missing')
    original=verify_toc(LIVE)
    shutil.copytree(STAGE,tmp)
    verify_toc(tmp)
    # Same-volume renames preserve original installation byte-for-byte.
    LIVE.rename(backup)
    try:
        tmp.rename(LIVE)
    except BaseException:
        if not LIVE.exists(): backup.rename(LIVE)
        raise
    result={'active':True,'state':'CANDIDATE_ACTIVE','backup':str(backup),
       'installed_toc_sha256':sha(LIVE/'ForeverRoute.toc'),
       'original_toc_sha256':original['toc_sha256'],
       'deployed_at':datetime.now(timezone.utc).isoformat()}
    save(result)
    return result


def rollback() -> dict:
    if wow_running():
        raise RuntimeError('WoW running: wait for clean client exit')
    if not MANIFEST.is_file():
        raise RuntimeError('No deployment manifest: refuse blind restore')
    d=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if not d.get('active'):
        return {'state':'ALREADY_RESTORED'}
    backup=Path(d['backup'])
    if not backup.is_dir() or not LIVE.is_dir():
        raise RuntimeError('Current addon or backup missing; manual intervention')
    if not backup.resolve().is_relative_to((WOW/'ForeverRoute_Backups').resolve()):
        raise RuntimeError('Unsafe backup path')
    verify_toc(backup)
    discarded=WOW/'ForeverRoute_Backups'/('LiveQA_candidate_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
    LIVE.rename(discarded)
    try:
        backup.rename(LIVE)
    except BaseException:
        if not LIVE.exists(): discarded.rename(LIVE)
        raise
    d.update(active=False,state='RESTORED',restored_at=datetime.now(timezone.utc).isoformat(),
             retired_candidate=str(discarded))
    save(d)
    return d

def report() -> dict:
    import re
    root=WOW/'WTF'/'Account'
    results=list(root.glob('*/SavedVariables/ForeverRouteLiveQA.lua')) if root.is_dir() else []
    if not results:
        return {'state':'NO_LIVE_RESULT', 'reason':'No character login/reload recorded yet'}
    file=max(results,key=lambda x:x.stat().st_mtime)
    raw=file.read_text(encoding='utf-8-sig',errors='replace')[:500000]
    def field(name):
        match=re.search(r'(?:\[\s*["\']'+re.escape(name)+r'["\']\s*\]|\b'+re.escape(name)+r')\s*=\s*["\']([^"\']{0,100})["\']',raw)
        return match.group(1) if match else None
    age=int(time.time()-file.stat().st_mtime)
    module_pattern=r'\{\s*\["loaded"\]\s*=\s*(true|false),\s*\["name"\]\s*=\s*"([^"]{1,90})",\s*\["healthy"\]\s*=\s*(true|false)'
    modules=[{'name':m.group(2),'loaded':m.group(1)=='true','healthy':m.group(3)=='true'}
             for m in re.finditer(module_pattern,raw)]
    def number_field(name):
        m=re.search(r'\["'+re.escape(name)+r'"\]\s*=\s*(\d+)',raw)
        return int(m.group(1)) if m else None
    return {'state':'LIVE_RESULT_RECORDED', 'age_seconds':age,
        'file_mtime_epoch':file.stat().st_mtime,
        'result':field('result') or 'UNPARSED', 'phase':field('phase') or 'UNKNOWN',
        'health':field('health') or 'UNKNOWN','modules_total':len(modules),
        'degraded_modules':[x['name'] for x in modules if not x['healthy']],
        'blocked_actions':number_field('blockedActions'),
        'forbidden_actions':number_field('forbiddenActions'),
        'lua_errors':'NOT_INSTRUMENTED'}


def status() -> dict:
    installed=PROBE.is_dir() and (PROBE/'ForeverRouteLiveQA.toc').is_file()
    loaded=json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.is_file() else {}
    return {'state':'READY_FOR_LAUNCH' if installed else 'PROBE_NOT_INSTALLED',
        'wow_running':wow_running(), 'battlenet_installed':Path(r'H:\Battle.net\Battle.net.exe').is_file(),
        'probe_installed':installed, 'candidate_staged':STAGE.is_dir(),
        'candidate_active':bool(loaded.get('active')), 'diagnostic':report()}


def launcher() -> dict:
    exe=Path(r'H:\Battle.net\Battle.net.exe')
    if not exe.is_file(): raise RuntimeError('Battle.net launcher missing')
    # Never start Wow.exe or attempt authentication via command arguments.
    processes=subprocess.run(['tasklist','/FI','IMAGENAME eq Battle.net.exe'],
                             capture_output=True,text=True,errors='replace',timeout=12)
    already='Battle.net.exe' in processes.stdout
    if not already:
        subprocess.Popen([str(exe)],cwd=str(exe.parent),close_fds=True)
    return {'state':'BATTLENET_ALREADY_RUNNING' if already else 'BATTLENET_LAUNCH_REQUESTED',
            'next':'Use existing launcher login, select WoW Forever, click Play. No credentials or character selection are automated.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['status','install-probe','stage','deploy','rollback','launch-battlenet','report','verify-live','verify-stage'])
    parser.add_argument('--allow-live',action='store_true')
    args=parser.parse_args()
    commands={'status':status,'install-probe':install_probe,
              'stage':stage_candidate,'deploy':lambda:deploy_candidate(args.allow_live),
              'rollback':rollback,'launch-battlenet':launcher,'report':report,
              'verify-live':lambda:verify_toc(LIVE),
              'verify-stage':lambda:verify_toc(STAGE)}
    try:
        data=commands[args.command]()
        print(json.dumps(data,ensure_ascii=False,indent=2))
    except Exception as e:
        print(json.dumps({'state':'ERROR','detail':str(e)},ensure_ascii=False),file=sys.stderr)
        raise SystemExit(2)

if __name__=='__main__': main()

def keep_verified(run_record: dict) -> dict:
    """Keep the tested candidate installed only on unequivocal real client PASS.

    Previous ForeverRoute is retained at manifest.backup permanently.
    This is a smoke-test promotion, not a release or route-completeness proof.
    """
    if wow_running():raise RuntimeError('Refuse promotion before WoW clean exit')
    if not MANIFEST.is_file():raise RuntimeError('Missing deployment manifest')
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if not manifest.get('active') or manifest.get('state')!='CANDIDATE_ACTIVE':
        raise RuntimeError('No active candidate deployment')
    q=(run_record.get('qa') or {})
    if (run_record.get('state')!='COMPLETE' or run_record.get('protected_popup_seen') or
        q.get('state')!='LIVE_RESULT_RECORDED' or q.get('result')!='PASS' or
        q.get('health')!='OK' or q.get('phase') not in ('WORLD_SETTLED','PLAYER_LOGOUT') or
        q.get('blocked_actions')!=0 or q.get('forbidden_actions')!=0 or
        q.get('modules_total',0)<15 or q.get('degraded_modules') or
        q.get('file_mtime_epoch',0)<run_record.get('started_at',0)):
        raise RuntimeError('Smoke probe not a clean, fresh, protected-action-free PASS')
    if sha(LIVE/'ForeverRoute.toc')!=manifest['installed_toc_sha256']:
        raise RuntimeError('Installed addon TOC changed after deployment')
    if not Path(manifest['backup']).is_dir():
        raise RuntimeError('Original version backup disappeared')
    manifest.update(active=False,state='KEPT_VERIFIED',verified_at=datetime.now(timezone.utc).isoformat(),
        result=q, protected_popup_seen=False, kept_backup=manifest['backup'])
    save(manifest)
    return manifest
