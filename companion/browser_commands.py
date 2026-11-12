"""Bounded browser commands, only explicit intents."""
import re
import unicodedata
import webbrowser
DESTINATIONS={"prohlizec":"https://www.google.com/","google":"https://www.google.com/","youtube":"https://www.youtube.com/","github":"https://github.com/"}
def normalize(value):
    value="".join(c for c in unicodedata.normalize("NFKD",value.casefold()) if not unicodedata.combining(c))
    return re.sub(r"\s+"," ",value.strip(" .!?"))
def intent(command):
    if not isinstance(command,str) or len(command)>120:return None
    phrase=re.sub(r"^(jarvisi|jarvis|prosim)\s+","",normalize(command))
    m=re.fullmatch(r"(?:otevri|spust|zapni)\s+(?:mi\s+)?(?:webovy\s+)?(prohlizec|google|youtube|github)",phrase)
    return m.group(1) if m else None
def execute(destination,opener=webbrowser.open):
    if destination not in DESTINATIONS:return {"status":"REFUSED","reply":"Nepovolena adresa."}
    try:accepted=bool(opener(DESTINATIONS[destination],new=2))
    except Exception:accepted=False
    if not accepted:return {"status":"FAILED","reply":"Prohlizec se nepodarilo spustit."}
    return {"status":"REQUESTED","reply":"Odeslal jsem prikaz otevrit "+DESTINATIONS[destination]+". Nacteni stranky nebylo overeno."}
