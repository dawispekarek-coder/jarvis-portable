"""Local, bounded self-study audit: verify learned method and suggest next skill.
NO web access, no cloud use, no code changes, no privilege escalation.
"""
import json,subprocess,sys,time
from pathlib import Path
import experience_learning as learning
ROOT=Path(__file__).resolve().parent.parent
REPORT=ROOT/'reports'/'self_learning_latest.json'
TESTS=('test_behavior_router','test_experience_learning','test_knowledge_refresh')

def recommend(stats):
    if stats['verified_observations']<6:
        return 'Sbírat další nezávisle ověřené zkušenosti z webového čtení; nevyvozovat obecné závěry z malého vzorku.'
    if stats['failed_reads']>stats['successful_reads']:
        return 'Ověřit záložní způsob čtení stránek v izolovaném testu; neměnit samovolně produkční nástroje.'
    return 'Ověřit novou drobnou dovednost na dosud neviděném testu a popsat její přínos.'

def run():
    command=[sys.executable,'-m','unittest','-q',*TESTS]
    try:
        output=subprocess.run(command,cwd=ROOT/'BrainCore',timeout=45,
            capture_output=True,text=True,errors='replace')
        passed=output.returncode==0 and 'OK' in (output.stdout+output.stderr)
        tests_text=(output.stdout+'\n'+output.stderr)[-1000:]
    except (OSError,subprocess.TimeoutExpired):
        passed=False;tests_text='INTERRUPTED_OR_UNAVAILABLE'
    stats=learning.summary()
    result={'date_utc_epoch':int(time.time()),'kind':'automated_local_self_review',
            'tests_passed':passed,'test_modules':list(TESTS),'test_tail':tests_text,
            'evidence':stats,'recommendation':recommend(stats),
            'changes_applied':False,'model_weights_retrained':False,
            'production_files_modified':False}
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    value=run()
    print(json.dumps({'passed':value['tests_passed'],'experience':value['evidence'],
           'report':str(REPORT)},ensure_ascii=True),flush=True)
    raise SystemExit(0 if value['tests_passed'] else 2)
