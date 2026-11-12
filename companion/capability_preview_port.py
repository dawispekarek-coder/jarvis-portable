from pathlib import Path
import shutil
p=Path("H:/RealJarvis/V2Sandbox/BrainCore/ui_compat.py")
data=p.read_text(encoding="utf-8")
old="'http://localhost:7353')"
new="'http://localhost:7353','http://127.0.0.1:7399','http://localhost:7399')"
if data.count(old)!=1: raise SystemExit("unexpected origin guard; abort")
new_data=data.replace(old,new,1)
compile(new_data,str(p),"exec")
backup=p.with_name("ui_compat.py.before_capability_preview_20261027.bak")
if backup.exists():raise SystemExit("backup already exists")
shutil.copy2(p,backup)
p.write_text(new_data,encoding="utf-8")
print("PREVIEW_ORIGIN_READY")
