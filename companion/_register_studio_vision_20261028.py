from pathlib import Path
import shutil
p=Path(r"H:\RealJarvis\V2Autonomy_20261027\BrainCore\companion_tools.py")
s=p.read_text(encoding="utf-8")
if "character_studio_visual_review" not in s:
 b=p.with_suffix(".before_studio_vision_20261028.py.bak")
 if not b.exists():shutil.copy2(p,b)
 needle=" registry.desktop=desktop"
 if needle not in s:raise SystemExit("Registry anchor missing")
 add=""" from companion_character_review import review as character_visual_review
 register('character_studio_visual_review','Compare original master reference against one new fullbody candidate using local vision model. Advisory QA never approves.',{'who':{'type':'string','enum':['lali','pooli']},'candidate_id':text_schema(90)},character_visual_review,write=True)
"""
 p.write_text(s.replace(needle,add+needle),encoding="utf-8")
print("STUDIO_VISION_REGISTERED")
