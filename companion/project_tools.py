"""One real, read-only ForeverRoute tool. Only fixed Git arguments and fixed checkout."""
from __future__ import annotations
import subprocess,re
from pathlib import Path

REPO=Path(r'H:\RealJarvis\AgentTeam\ForeverRouteDev')
GIT=Path(r'C:\Program Files\Git\cmd\git.exe')
SENSITIVE=re.compile(r'(?i)(secret|token|credential|password|\.env|api[_-]?key|private)')
TRIGGER=('git','repozit','větev','vetev','commit','změněné soubory','zmenene soubory','pracovní strom','pracovni strom')

def extract(text:str)->bool:
    if not isinstance(text,str):return False
    t=text.casefold().strip()
    if t in ('/git','/repo','/repo status','stav gitu','git status','stav repozitáře'):
        return True
    return ('foreverroute' in t and any(x in t for x in TRIGGER) and not
      any(x in t for x in ('oprav','přepiš','prepis','zapiš','zapis','commitni','pushni','smaž')))

def git(*args:str)->str:
    if not GIT.is_file() or not (REPO/'.git').exists():
        raise RuntimeError('checkout_not_found')
    cmd=[str(GIT),'--no-optional-locks','-C',str(REPO),*args]
    result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',
                          errors='replace',timeout=10,check=False)
    if result.returncode:
        raise RuntimeError('git_read_failed')
    return result.stdout.strip()

def status()->dict:
    root=git('rev-parse','--show-toplevel')
    if Path(root).resolve()!=REPO.resolve():
        raise RuntimeError('unexpected_checkout')
    branch=git('branch','--show-current') or '(detached HEAD)'
    commit=git('log','-1','--format=%h|%cs|%s')
    fields=commit.split('|',2)
    if len(fields)!=3: raise RuntimeError('unexpected_commit_format')
    short=git('status','--porcelain=v1','--untracked-files=normal')
    changed=[line for line in short.splitlines() if line]
    displayed=[]
    for line in changed[:12]:
        shown='[sensitive filename hidden]' if SENSITIVE.search(line) else line[:155]
        displayed.append(shown)
    return {'branch':branch[:150],'commit':fields[0],'date':fields[1],
       'subject':fields[2][:180],'clean':not bool(changed),
       'changed_count':len(changed),'changed_files':displayed,
       'read_only':True}

def format_status(result:dict)->str:
    state='Čistý pracovní strom – žádné lokální změny.' if result['clean'] else (
        'Změněných/nezařazených položek: '+str(result['changed_count'])+'.')
    message=(f"Skutečná kontrola Gitu ForeverRoute (pouze čtení):\n"
      f"Větev: {result['branch']}\n"
      f"Poslední commit: {result['commit']} ({result['date']})\n"
      f"Popis: {result['subject']}\n{state}")
    if result['changed_files']:
        message+='\nSoubory (výběr):\n'+'\n'.join('- '+p for p in result['changed_files'])
    return message+'\nTohle je stav repozitáře, nikoli potvrzení, že addon funguje ve hře.'

IDENTIFIER=re.compile(r"^[A-Za-z_][A-Za-z0-9_]{3,79}$")

def extract_code_search(text:str)->str|None:
    if not isinstance(text,str):return None
    message=text.strip()
    pats=(
      r"^/code\s+([A-Za-z_][A-Za-z0-9_]{3,79})$",
      r"^najdi\s+v\s+k[oó]du\s+ForeverRoute\s*:\s*([A-Za-z_][A-Za-z0-9_]{3,79})$",
      r"^najdi\s+funkci\s+([A-Za-z_][A-Za-z0-9_]{3,79})\s+ve\s+ForeverRoute$")
    for pat in pats:
        m=re.fullmatch(pat,message,re.I)
        if m:return m.group(1)
    return None

def search_lua(symbol:str)->dict:
    if not isinstance(symbol,str) or not IDENTIFIER.fullmatch(symbol) or SENSITIVE.search(symbol):
        raise ValueError("invalid_symbol")
    if not GIT.is_file() or not (REPO/".git").exists():
        raise RuntimeError("checkout_not_found")
    cmd=[str(GIT),"--no-optional-locks","-C",str(REPO),
         "grep","-n","-F","-i","-m","2","-e",symbol,"--","*.lua"]
    result=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",
                          errors="replace",timeout=11,check=False)
    if result.returncode not in (0,1):raise RuntimeError("git_grep_failed")
    matched=[]
    for entry in result.stdout.splitlines():
        parts=entry.split(":",2)
        if len(parts)!=3:continue
        file,line,content=parts
        if SENSITIVE.search(file) or not file.lower().endswith(".lua"):continue
        if not line.isdigit() or int(line)<=0:continue
        matched.append({"file":file[:135],"line":int(line),"excerpt":content.strip()[:160]})
        if len(matched)>=8:break
    return {"symbol":symbol,"matches":matched,"read_only":True}
def format_code_search(data:dict)->str:
    if not data["matches"]:
        return ("Ve sledovaných Lua zdrojových souborech ForeverRoute jsem "
                "nenašel výskyt "+data["symbol"]+". Nic jsem nezměnil.")
    rows=[f"- {hit['file']}:{hit['line']} — {hit['excerpt']}" for hit in data["matches"]]
    return ("Skutečné nalezené výskyty v Lua kódu ForeverRoute (pouze čtení):\n"+
            "\n".join(rows)+
            "\nJde o nalezené řádky, nikoli o ověřenou opravu nebo provedenou změnu.")