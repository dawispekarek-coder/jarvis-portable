"""Deterministic audits on retrieved web evidence. No model or OS actions."""
import re
from urllib.parse import urlparse
MAX_OPEN=3
MAX_ATTEMPTS=5
NUMBER=re.compile(r"(?<![\w])(\d+(?:[.,]\d+)?)\s*(%|GB|MB|ms|seconds?|minutes?|tests?|testů|checks?|kontrol)\b",re.I)
WORDS=re.compile(r"[\w]{4,}")
STOP={"with","that","this","from","about","are","the","and","for","both","also","when","which","dnes","jako","nebo","jsou","bude","pouze"}
def host(page):
    return (urlparse(page.get("url","")).hostname or "").lower()
def diverse_candidates(links):
    first=[];again=[];seen=set()
    for hit in links:
        h=host(hit)
        if not h:continue
        (again if h in seen else first).append(hit)
        seen.add(h)
    return (first+again)[:MAX_ATTEMPTS]
def claims(page):
    output=[]
    text=page.get("excerpt","")[:2000]
    for sentence in re.split(r"(?<=[.!?])\s+|\n+",text):
        if not 12<=len(sentence)<=300:continue
        for m in NUMBER.finditer(sentence):
            context=sentence[max(0,m.start()-90):min(len(sentence),m.end()+70)]
            tokens={x.casefold() for x in WORDS.findall(context) if x.casefold() not in STOP}
            unit=m.group(2).casefold()
            if unit in ("testů","test"):unit="tests"
            if unit=="kontrol":unit="checks"
            output.append({"value":m.group(1).replace(",","."),"unit":unit,
                "context":context.strip()[:165],"tokens":tokens,"url":page.get("url","")})
    return output[:12]
def possible_conflicts(pages):
    out=[];seen=set()
    for i,left in enumerate(pages):
        for j,right in enumerate(pages):
            if j<=i or host(left)==host(right):continue
            for a in claims(left):
                for b in claims(right):
                    if a["unit"]!=b["unit"] or a["value"]==b["value"]:continue
                    if len(a["tokens"] & b["tokens"])<2:continue
                    key=(i,j,a["unit"])
                    if key in seen:continue
                    seen.add(key)
                    out.append({"first":i+1,"second":j+1,"unit":a["unit"],
                        "values":[a["value"],b["value"]],                        "contexts":[a["context"],b["context"]]})
                    if len(out)>=3:return out
    return out
def assess(bundle):
    pages=bundle.get("pages",[])
    domains={host(p) for p in pages if host(p)}
    differences=possible_conflicts(pages)
    if differences:
        check="Možné rozdílné číselné údaje porovnat s primárním zdrojem; mohou popisovat odlišné věci."
    elif len(domains)<2:
        check="Vyhledat druhý nezávislý zdroj, protože z jediné domény nelze potvrdit shodu."
    elif bundle.get("read_failures"):
        check="Dohledat nepřístupné zdroje a zkontrolovat jejich aktuálnost."
    else:
        check="Před zásadním rozhodnutím ověřit datum a původ zveřejněných tvrzení."
    return {"readable_pages":len(pages),"independent_domains":len(domains),
        "potential_numeric_mismatches":differences,
        "sources_limited":len(domains)<2,"recommended_verification":check}
