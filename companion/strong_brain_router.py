"""Opt-in FREE hosted adviser; no local PC actions or direct credential access.
Uses the existing free-only Hermes/OmniRoute relay (may have web search); no paid fallback.
"""
import json,re,subprocess,sys
from pathlib import Path
from general_brain import generate,unconnected_action
ROOT=Path(r'H:\RealJarvis\AgentBrainSandbox')
RUNNER=ROOT/'hermes_primary_turn.py'
PREFIXES=('silnější ai:','silnejsi ai:','/strong ','/strong:')
BAD_TEXT=('Ă','Ä','Ĺ','â€','Â','Ľ')
SENSITIVE=re.compile(r'(?i)(password|heslo|api[_-]?key|private[_-]?key|bearer|sk-[a-z0-9]{8,})')

def extract(text):
    if not isinstance(text,str):return None
    value=text.strip()
    for prefix in PREFIXES:
        if value.casefold().startswith(prefix):return value[len(prefix):].strip()
    return None

def cloud_quality(text):
    if not isinstance(text,str) or not 4<=len(text.strip())<=2000:return False
    if text.lstrip().startswith(('{"tool"','<tool_call','<|')):return False
    if sum(text.count(x) for x in BAD_TEXT)>=2:return False
    return True
def free_cloud(question,timeout=55):
    if not isinstance(question,str) or not 3<=len(question.strip())<=650:
        return {'status':'INVALID_REQUEST','answer':''}
    if SENSITIVE.search(question):
        return {'status':'SENSITIVE_TEXT_REJECTED','answer':''}
    if not RUNNER.is_file():
        return {'status':'HOSTED_RUNNER_MISSING','answer':''}
    try:
        result=subprocess.run([sys.executable,str(RUNNER),question.strip()],
            cwd=str(ROOT),capture_output=True,text=True,errors='replace',timeout=timeout)
        data=json.loads(result.stdout.strip())
        if result.returncode or data.get('status')!='MODEL_RESPONSE' or data.get('result_exit')!=0:
            return {'status':'HOSTED_UNAVAILABLE','answer':''}
        answer=data.get('answer','')
        if not cloud_quality(answer):
            return {'status':'HOSTED_QUALITY_REJECTED','answer':''}
        return {'status':'HOSTED_UNVERIFIED','answer':answer.strip(),
                'provider':'free-only-omniroute'}
    except (OSError,ValueError,TypeError,subprocess.TimeoutExpired):
        return {'status':'HOSTED_UNAVAILABLE','answer':''}

def answer(question,history=(),notes=None):
    """Opt-in cloud for question only, fallback to local model on any fault."""
    if unconnected_action(question):
        return {'status':'NO_TOOL_ACCESS','reply':'Tato verze neumí vykonávat příkazy na PC ani upravovat soubory.'}
    result=free_cloud(question)
    if result['status']=='HOSTED_UNVERIFIED':
        return {'status':'HOSTED_UNVERIFIED','reply':'Bezplatná externí AI (neověřená odpověď):\n'+result['answer']}
    if result['status'] in ('INVALID_REQUEST','SENSITIVE_TEXT_REJECTED'):
        return {'status':result['status'],'reply':'Tento dotaz nelze bezpečně odeslat externímu modelu. Nic jsem neodeslal.'}
    try:
        local=generate(question,history=history,notes=notes)
        return {'status':'LOCAL_FALLBACK','reply':'Silnější model nebyl dostupný nebo neprošel kontrolou. Přepnul jsem na lokální AI.\n\n'+local['reply']}
    except Exception:
        return {'status':'BOTH_UNAVAILABLE','reply':'Silnější ani lokální model neodpověděl spolehlivě. Nic jsem neprovedl.'}