"""RealJarvis V2: verify internet, reconnect only ONE already-saved Wi-Fi profile if offline.
No passwords, no arbitrary networking commands, no model-generated shell execution.
"""
from __future__ import annotations
import re,socket,subprocess,unicodedata
from urllib.parse import urlparse
import httpx
PROBE="https://www.python.org/"
NAMES=("napoj se na internet","pripoj se na internet","pripoj se k internetu",
 "pripoj internet","zapni internet","zprovozni internet",
 "obnov internet","aktivuj internet","zkontroluj internet",
 "zkontroluj pripojeni k internetu","over internet","otestuj internet",
 "mam internet","mas internet","jsi na internetu","jsi pripojeny k internetu",
 "je internet pripojeny","pripoj se k siti")
ACTION=("napoj","pripoj","zapni","zprovozni","obnov","aktivuj")
def normalize(text:str)->str:
    value="".join(c for c in unicodedata.normalize("NFKD",text.casefold())
                  if not unicodedata.combining(c))
    value=re.sub(r"[^a-z0-9 ]+"," ",value)
    return " ".join(value.split())
def intent(text:str)->str|None:
    if not isinstance(text,str) or len(text)>250:return None
    words=normalize(text)
    words=re.sub(r"^(jarvisi|jarvis|prosim|pane)\s+", "", words)
    words=re.sub(r"\s+prosim$", "", words)
    if words in NAMES:
        return "connect" if words.startswith(ACTION) else "check"
    return None
def https_probe()->dict:
    try:
        resolved=socket.getaddrinfo("www.python.org",443,type=socket.SOCK_STREAM)
        if not resolved:raise OSError("no_dns_answers")
    except (OSError,ValueError) as error:
        return {"connected":False,"dns_ok":False,"https_ok":False,"reason":"dns_unavailable"}
    try:
        with httpx.Client(timeout=9,follow_redirects=False,trust_env=False) as client:
            r=client.get(PROBE,headers={"User-Agent":"RealJarvis2-ConnectivityCheck/1.0"})
        valid=(r.status_code==200 and "python" in r.text[:5000].casefold())
        return {"connected":valid,"dns_ok":True,"https_ok":valid,
                "reason":"ok" if valid else "https_unavailable"}
    except (httpx.HTTPError,ValueError,UnicodeError):
        return {"connected":False,"dns_ok":True,"https_ok":False,
                "reason":"https_unavailable"}
def wifi_saved_profiles()->list[str]:
    try:
        p=subprocess.run(["netsh","wlan","show","profiles"],capture_output=True,
            text=True,errors="replace",timeout=8,check=False)
    except (OSError,subprocess.TimeoutExpired):return []
    if p.returncode!=0:return []
    profiles=[]
    for line in p.stdout.splitlines():
        found=re.match(r"^\s*(?:All User Profile|Profil všech uživatelů)\s*:\s*(.+)\s*$",line,re.I)
        if found:
            name=found.group(1).strip()
            if name and len(name)<130 and name not in profiles:profiles.append(name)
    return profiles
def reconnect_saved_wifi()->str:
    profiles=wifi_saved_profiles()
    if len(profiles)!=1:return "no_unique_saved_wifi"
    try:
        r=subprocess.run(["netsh","wlan","connect","name="+profiles[0]],
            capture_output=True,text=True,errors="replace",timeout=12,check=False)
        return "requested" if r.returncode==0 else "reconnect_rejected"
    except (OSError,subprocess.TimeoutExpired):
        return "reconnect_error"
def check_or_connect(action:str="check",probe=https_probe,reconnect=reconnect_saved_wifi,
                     search_probe=None)->dict:
    if action not in ("check","connect"):raise ValueError("invalid_action")
    first=probe()
    result={**first,"requested_action":action,"reconnect_attempted":False,
            "reconnect_result":"not_needed","web_search_ready":False}
    if not result["connected"] and action=="connect":
        result["reconnect_attempted"]=True
        result["reconnect_result"]=reconnect()
        result.update(probe())
    if result["connected"]:
        try:
            if search_probe is None:
                from public_search import search
                search_probe=lambda:bool(search("Python documentation").get("results"))
            result["web_search_ready"]=bool(search_probe())
        except Exception:result["web_search_ready"]=False
    return result
def format_result(result:dict)->str:
    if result["connected"]:
        status=("Internet JE připojený a ověřený: DNS a HTTPS skutečně fungují "
            "(https://www.python.org/, HTTP 200). Není potřeba žádné další připojování.")
        if result["web_search_ready"]:
            return status+"\nWebové vyhledávání Jarvise je také dostupné. Zadej třeba „Najdi zprávy o World of Warcraft“."
        return status+"\nSamotné vyhledávání není momentálně ověřené. Mohu zkusit jeho diagnostiku, ale nebudu předstírat výsledky."
    if result["reconnect_attempted"]:
        return ("Připojení k internetu se zatím nepodařilo ověřit. "
                "Pokus o obnovení uložené Wi-Fi: "+result["reconnect_result"]+
                ". Nebudu bez ověření tvrdit, že jsme online.")
    return ("Internetové připojení nyní není ověřené ("
            +result.get("reason","unknown")+"). Žádné připojení jsem neměnil.")
