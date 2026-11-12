"""Page-authored date labels. These are hints, NEVER proof that claims are current."""
import re
from datetime import date
DATE_LABEL=re.compile(
 r"(?:last\s+updated|updated\s+on|last\s+modified|published(?:\s+on)?|"
 r"aktualizov[áa]no|publikov[áa]no)\s*[:\-]?\s*"
 r"(\d{4}-\d{2}-\d{2})",re.I)
def date_hints(pages):
 found=[]
 for i,page in enumerate(pages,1):
  text=page.get('excerpt','')[:3000]
  match=DATE_LABEL.search(text)
  if not match:continue
  raw=match.group(1)
  try:when=date.fromisoformat(raw)
  except ValueError:continue
  status='future_label' if when>date.today() else 'page_claim_only'
  found.append({'source':i,'date':raw,'status':status})
 return found
def freshness_message(pages):
 hints=date_hints(pages)
 if not pages:return 'Aktuálnost: nebyly načteny žádné stránky.'
 if not hints:return 'Aktuálnost: u načtených úryvků nebylo zjištěno jednoznačně označené datum aktualizace či publikace.'
 values=', '.join('['+str(p['source'])+'] '+p['date'] for p in hints)
 return ('Aktuálnost: datum uvedené samotnými stránkami: '+values+
         '. Údaj nebyl nezávisle ověřen a nepotvrzuje aktuálnost všech tvrzení.')