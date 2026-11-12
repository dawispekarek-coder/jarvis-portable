"""Safely integrate capability inventory into the V2 chat and prompt."""
from pathlib import Path
import os, tempfile, datetime, shutil
base=Path("H:/RealJarvis/V2Sandbox/BrainCore")
def modify(filename, edits):
 p=base/filename
 old=p.read_text(encoding="utf-8")
 new=old
 for before,after in edits:
  count=new.count(before)
  if count!=1: raise RuntimeError(f"{filename}: expected one anchor, found {count}: {before[:45]}")
  new=new.replace(before,after,1)
 if old==new: raise RuntimeError("unchanged: "+filename)
 compile(new,str(p),"exec")
 backup=p.with_name(p.name+".before_capabilities_20261027.bak")
 if backup.exists(): raise RuntimeError("backup already exists: "+str(backup))
 shutil.copy2(p,backup)
 fd,tmp=tempfile.mkstemp(prefix="cap_",suffix=".py",dir=str(base))
 try:
  with os.fdopen(fd,"w",encoding="utf-8",newline="") as f: f.write(new)
  os.replace(tmp,p)
 except BaseException:
  if os.path.exists(tmp):os.unlink(tmp)
  raise
 print("PATCHED",filename,"BACKUP",backup.name)
modify("general_brain.py",[
 ("from behavior_router import OPERATOR_RULES","from behavior_router import OPERATOR_RULES\nfrom capability_inventory import model_context"),
 ('SYSTEM += " " + OPERATOR_RULES','SYSTEM += " " + OPERATOR_RULES + "\\n" + model_context()')
])
modify("ui_compat.py",[
 ("import knowledge\n","import knowledge\nfrom capability_inventory import inventory as capability_inventory, answer as capability_answer\n"),
 ('@app.get(\'/api/tts/status\')\ndef voice_status():return {\'available\':False,\'provider\':\'disabled-in-v2\'}',
  '@app.get(\'/api/capabilities\')\ndef capabilities():return capability_inventory()\n@app.get(\'/api/tts/status\')\ndef voice_status():return {\'available\':False,\'provider\':\'not-connected-in-v2\',\'external_backend\':capability_inventory()[\'tts_external_service\']}'),
 ("            browser_action=browser_intent(text)",
  "            # Live and deterministic self-knowledge before model or action routing.\n            self_knowledge=await asyncio.to_thread(capability_answer,text)\n            if self_knowledge is not None:\n                await notify(ws,'info',text='V2: live capability registry (read-only)')\n                await notify(ws,'assistant',text=self_knowledge,speak=False)\n                await notify(ws,'done')\n                continue\n            browser_action=browser_intent(text)")
])
