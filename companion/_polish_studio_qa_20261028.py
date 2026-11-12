from pathlib import Path
B=Path(r"H:\RealJarvis\V2Autonomy_20261027\BrainCore")
p=B/"companion_image_provider.py"
s=p.read_text(encoding="utf-8")
needle="BIG BRIGHT PINK BOW on top of her head, no shirt and no hoodie"
rep="EXACTLY ONE BIG BRIGHT PINK BOW ON TOP OF HEAD (no second bow at neck, no bowtie), no shirt and no hoodie"
if needle in s:
 s=s.replace(needle,rep);p.write_text(s,encoding="utf-8")
q=B/"companion_character_review.py"
t=q.read_text(encoding="utf-8")
old="Compare two character images. IMAGE 1 is the authoritative original of "
new="Compare two ORIGINAL independently-created cartoon characters. Do not invent any movie, franchise or source attribution. IMAGE 1 is the authoritative original of "
if old in t:
 t=t.replace(old,new);q.write_text(t,encoding="utf-8")
api=B/"companion_api.py"
a=api.read_text(encoding="utf-8")
if "'image_model':'disabled'" in a:
 a=a.replace("'image_model':'disabled'","'image_model':'external_sdxl_experimental_text_only_not_master'")
 api.write_text(a,encoding="utf-8")
print("IDENTITY_MODEL_AND_UI_TRUTH_PATCHED")
