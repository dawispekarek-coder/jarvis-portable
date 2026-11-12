from pathlib import Path
from companion_character_studio import ROOT, load, status
from companion_store import Store
from companion_settings import STATE, ROOT as JROOT
d=load()
assert status()["verified"]
rules="""JARVIS LALI AND POOLI REUSABLE ART STANDARD
These two characters have fixed immutable original reference art in Godot/studio_library.
Reuse approved MASTER poses and fullframe cycles from library for EVERY new video.
Never regenerate whole character identity per video; new poses are stored as candidates,
compared visually to original, and require explicit approval before master promotion.
Never animate sliced/cropped limbs or false character turns.
Use 2dimg2motion ONLY to generate and validate full body keyposes and inbetweens.
Godot builds films from approved, reusable assets, real expression and scene changes.
Free OVH SDXL is PROMPT ONLY and NOT character-reference-conditioned: studies, not master art.
Call character_studio_plan_story first to enumerate reusable and missing assets.
Current: original Lali/Pooli and 5 expression references per character are locked.
No approved complete multi-angle redraws or walking loops yet. No professional Reel yet.
Do not publish, pay, overwrite masters, or claim quality until verified and owner approved.
"""
p=JROOT/"KnowledgeInbox"/"LALI_POOLI_REUSABLE_MASTER_20261028.md"
p.write_text(rules,encoding="utf-8")
(ROOT/"MASTER_RULES.txt").write_text(rules,encoding="utf-8")
Store(STATE).remember("skill:lali_pooli_master_reuse",rules,"verified_studio_policy")
html=["<!doctype html><html><meta charset='utf-8'><title>Jarvis Studio Lali Pooli</title><style>body{font:18px Arial;background:#f6f2ed;margin:30px}section{display:flex;gap:22px}.box{background:#fff;border-radius:18px;padding:15px;width:48%}img{object-fit:contain;max-width:100%;height:300px}figure{display:inline-block;margin:5px}figure img{height:130px}small{display:block}</style><h1>Character Studio / Lali &amp; Pooli</h1><p>Official originals locked. Expressions below are references only. New study is NOT APPROVED.</p><section>"]
for w in ("lali","pooli"):
 html.append("<div class='box'><h2>"+w.capitalize()+"</h2><img src='refs/"+w+"/fullbody.png'><div>")
 for emotion in d["characters"][w]["references"]["emotions"]:
  html.append("<figure><img src='refs/"+w+"/"+emotion+".png'><small>"+emotion+"</small></figure>")
 html.append("</div></div>")
html.append("</section><h2>Unapproved generated studies</h2>")
for w in ("lali","pooli"):
 for id,rec in d["characters"][w]["candidates"].items():
  html.append("<figure><img src='"+rec["file"]+"'><small>"+id+" - UNAPPROVED</small></figure>")
html.append("</html>")
(ROOT/"CHARACTER_BIBLE.html").write_text("\n".join(html),encoding="utf-8")
print("BIBLE_READY",ROOT/"CHARACTER_BIBLE.html")
print("KNOWLEDGE_READY",p)
print("SAVED_MEMORY_AND_INTEGRITY",status()["verified"])
