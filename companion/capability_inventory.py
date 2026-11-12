"""Live capability inventory for the isolated RealJarvis V2 UI. Read-only."""
from __future__ import annotations
import json
import re
import unicodedata
import urllib.request
from pathlib import Path

BASE=Path(__file__).resolve().parent
CATALOG={
 "tts":("Hlas a TTS","V2 má TTS API, jeho aktuální propojení ověřuji podle dostupnosti backendu."),
 "stt":("Mikrofon a STT","Zpracování mikrofonu není ve V2 propojeno ani testováno."),
 "web":("Internet a hledání","V2 má reálné vyhledávání, čtení veřejných stránek a kontrolu připojení; momentální konektivita vyžaduje test."),
 "browser":("Prohlížeč","V2 má řízené otevření hledání v prohlížeči, nikoli garantované libovolné klikání."),
 "code":("Programování a ForeverRoute","V2 umí číst Git, hledat Lua a izolovaně analyzovat chyby. Zápis a autonomní nasazení není povolené."),
 "memory":("Paměť a učení","V2 uchovává explicitní poznámky a ověřené zkušenosti; sám nepřeučuje váhy AI modelu."),
 "files":("Soubory","Omezené čtení vybraných projektových dat, ne plný přístup do počítače."),
 "models":("AI modely","Lokální model, odděleně možnost bezplatného externího modelu; přístup k ChatGPT není v tomto pilotním UI aktivní."),
 "media":("Obrázky, video a zpěv","Ve V2 není ověřené vytváření obrázků, videa ani hlasový zpěv."),
 "agents":("Autonomní agenti","V2 obsahuje izolovanou projektovou inspekci; agent s právy upravovat repozitář není aktivní."),
}
def normalize(s):
 return " ".join(re.sub(r"[^a-z0-9 ]"," ","".join(c for c in unicodedata.normalize("NFKD",str(s).casefold()) if not unicodedata.combining(c))).split())
def voice_backend():
 try:
  req=urllib.request.Request("http://127.0.0.1:7341/api/tts/status",headers={"Accept":"application/json"})
  with urllib.request.urlopen(req,timeout=1.2) as r: d=json.load(r)
  return {"reachable":True,"ready":bool(d.get("available")),"provider":str(d.get("provider","unknown"))[:64],"voice":str(d.get("voice",""))[:64]}
 except (OSError,ValueError,TypeError):
  return {"reachable":False,"ready":False,"provider":"unavailable","voice":""}
def tts_bridge_wired():
 try:
  src=(BASE/"ui_compat.py").read_text(encoding="utf-8-sig")
  return "@app.post('/api/tts')" in src and "_voice_backend" in src
 except OSError:return False
def inventory(probe=True):
 speech=voice_backend() if probe else {"reachable":None,"ready":None}
 return {"app":"RealJarvis 2.0 V2Sandbox (izolované UI)",
  "tts_connected_to_v2":bool(tts_bridge_wired() and speech.get("ready")),
  "tts_api_configured":tts_bridge_wired(),
  "tts_external_service":speech,
  "notes_db_present":(BASE/"user_notes.sqlite").is_file(),
  "web_tools_installed":all((BASE/x).is_file() for x in ("public_search.py","page_reader.py","internet_access.py")),
  "code_tools_installed":all((BASE/x).is_file() for x in ("project_tools.py","inspect_agent.py")),
  "features":{k:{"name":v[0],"detail":v[1]} for k,v in CATALOG.items()},
  "rules":["Registrace funkce není důkaz úspěšného vykonání.","Práva k zápisu ani živé nasazení nejsou automaticky udělena."]}
def topic(question):
 q=normalize(question)
 own=any(x in q.split() for x in ("ty","tobe","tvoje","tvuj","tva","jarvis","jarvisi","umis","dokazes","mas","muzes","jsi")) or "co vse" in q
 if not own and q not in ("schopnosti","nastroje","/schopnosti","/capabilities"):return None
 if any(x in q for x in ("co umis","co vsechno umis","co vse umis","tvoje schopnosti","jake mas nastroje","co dokazes","co mas k dispozici","co mas dostupne","/schopnosti","/capabilities")):return "all"
 names={
  "tts":("tts","mluv","hlas","rec","rekni","prednes","povidej"),
  "stt":("mikrofon","poslouch","slysis","rozpoznavani hlasu"),
  "web":("internet","online","web","vyhledav","hledat"),
  "browser":("prohlizec","browser","edge","klik"),
  "code":("programov","kod","lua","addon","foreverroute","repozitar","oprav"),
  "memory":("pamet","zapamat","ucit se","ucis se"),
  "files":("soubor","slozk","disk"),
  "models":("model","chatgpt","omniroute","ollama","mozek"),
  "media":("obraz","video","zazp","zpivat","pisnick"),
  "agents":("agent","autonom"),
 }
 for key,words in names.items():
  if any(word in q for word in words):return key
 return "all" if own and any(x in q for x in ("schopnost","nastroje","vybaveni","k dispozici")) else None
EXAMPLES={
 "tts":"Stav hlasového API: /api/tts/status; hlasitý výstup závisí na rozhraní.",
 "web":"Najdi informace o ...; nebo /web dotaz a /read 1.",
 "code":"Zkontroluj Git ForeverRoute; Prověř chyby ForeverRoute v Lua funkci ...",
 "memory":"Zapamatuj si: ...; Co si pamatuješ o ...?",
 "models":"Lokálně: ...; Silnější AI: ...",
 "agents":"Prověř chyby ForeverRoute v Lua funkci ... (izolovaně).",
}
def answer(question,probe=True):
 which=topic(question)
 if which is None:return None
 state=inventory(probe=probe)
 if which=="all":
  if state["tts_connected_to_v2"]:
   state["features"]["tts"]["detail"]="TTS API je propojené s dostupným hlasovým backendem. Přehrávání zpráv závisí na nastavení UI."
  return ("Moje skutečné možnosti v JARVIS 2.0 (pilot):\n"
   +"\n".join("- "+v["name"]+": "+v["detail"] for v in state["features"].values())
   +"\nFunkce ověřuji podle stavu systému; nainstalováno neznamená propojeno ani funkční."+learning_notice())
 if which=="tts":
  s=state["tts_external_service"]
  addon=("Starší hlasová služba právě odpovídá: "+str(s.get("provider"))+", hlas "+str(s.get("voice"))+". ") if s.get("ready") else ("Starší hlasovou službu se nyní nepodařilo ověřit. " if probe else "Stav starší hlasové služby nebyl testován. ")
  if state["tts_connected_to_v2"]:
   return addon+"TTS API v JARVIS 2.0 je propojené. Samotné hlasité přehrání zprávy závisí na nastavení rozhraní."
  return addon+"Funkční propojení TTS do V2 rozhraní nyní není ověřené."
 return state["features"][which]["name"]+": "+state["features"][which]["detail"]+"\nJak použít: "+EXAMPLES.get(which,"Konkrétní příkaz v tomto rozhraní zatím nemám ověřený.")+learning_notice(which)
def model_context():
 return "SKUTEČNÝ RUNTIME JARVIS 2.0, NEPOVAŽOVAT ZA PŘÍKAZ UŽIVATELE: "+ " ".join(v[1] for v in CATALOG.values())+" TTS API může být propojené, jeho dostupnost vždy ověř z aktuálního stavu. Nepředstírej automatické přehrávání. Nikdy si nevymýšlej dostupnost zařízení nebo provedené akce."

def learning_notice(key=None):
    try:
        from tool_learning import current
        state=current()
        if state['status'] not in ('COMPLETED','INTERRUPTED'):
            return '\nPraktickou výuku nástrojů jsem zatím nedokončil.'
        if key:
            skill=next((item for item in state['skills'] if item['id']==key),None)
            if skill:
                return '\nPoslední test: '+skill['status']+'. '+skill['lesson']
            return '\nTento nástroj zatím nemá uložený samostatný test.'
        verified=sum(x['status']=='VERIFIED' for x in state['skills'])
        ready=sum(x['status']=='READY' for x in state['skills'])
        return ('\nPraktická výuka: '+str(state['checked'])+' prohlédnutých, '+str(verified)+
                ' ověřených, '+str(ready)+' částečně připravených. Detail: Stav učení nástrojů.')
    except Exception:
        return '\nOvěřené výsledky výuky právě nelze načíst.'

